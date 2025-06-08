# Introduction

This is a description of the installation of a FastAPI LibreOffice rest server, which allows Moodle to use a separate server for document conversion.

The sources and websites I used can be found below under [Useful links](#useful-links).

## 0. Prerequisites
Before starting this guide, you should have:

* A server with Ubuntu or Debian installed.

## 1. Install required software
```
apt install curl wget vim git

apt install python3-pip python3-dev python3-venv

apt install nginx

apt install libreoffice
```
Check if soffice is in the path and a conversion with a [sample file](https://filesamples.com/formats/docx) works.

```
soffice --headless --convert-to pdf sample1.docx
```

## 2. Add a new user
Create a new non-root user called `fastapi-user` and remove the password. 

```
useradd -m fastapi-user
passwd -d fastapi-user
usermod --shell /bin/bash fastapi-user
```
Work with the `fastapi-user` account.

```
su fastapi-user
```
Change to the HOME directory, clone the Repositors and move the folder `my_fastapi_project`.

```
cd ~
git clone https://github.com/miotto/server_fileconverter_fastapisoffice.git
mv ~/server_fileconverter_fastapisoffice/my_fastapi_project .
```
## 3. Install Python packages and test the application
Install some Python packages in the virtual environment (work with the `fastapi-user` account).

Change to the Project folder, create a Python virtual environment and activate it. 

```
cd ~/my_fastapi_project/
python3 -m venv .venv
source .venv/bin/activate
```
Install some Python packages in the virtual Pytohn environment.

```
pip install fastapi gunicorn uvicorn
pip install python-multipart
pip install werkzeug
```
Check the file `~/my_fastapi_project/config.py` if the upload directory is set correctly.

Test the FastAPI app:

```
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app

or

gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --log-level debug
```
To test, execute the following command from another terminal on the same server.

```
curl -F 'file=@/home/fastapi-user/sample1.docx' http://127.0.0.1:8000/upload
```
Output

```
{"result":{"pdf":"/upload/pdf/sample1.pdf","source":"/upload/source/sample1.docx"}}
```
If everything is ok, the result file is in folder

```
~/my_fastapi_project/tmp/pdf
```

## 4. Create a Gunicorn Script
Create a Gunicorn Script to start the service automatically.

As `fastapi-user` view the file, adapt it if necessary and make it executable.

```
vi ~/my_fastapi_project/gunicorn_start
```

```
#!/bin/bash
NAME=my-project
DIR=/home/fastapi-user/my_fastapi_project
USER=fastapi-user
GROUP=fastapi-user
WORKERS=4
WORKER_CLASS=uvicorn.workers.UvicornWorker
VENV=$DIR/.venv/bin/activate
BIND=127.0.0.1:8000
LOG_LEVEL=debug
LOG_FILE=/home/fastapi-user/my_fastapi_project/logs/my_fastapi_project.log

cd $DIR
source $VENV
exec gunicorn main:app \
  --name $NAME \
  --workers $WORKERS \
  --worker-class $WORKER_CLASS \
  --user=$USER \
  --group=$GROUP \
  --bind=$BIND \
  --log-level=$LOG_LEVEL \
  --log-file=$LOG_FILE
```

## 5. Install und configure Supervisor for Gunicorn
Install Supervisor as root user.

```
apt install supervisor
```
Create a supervisor configuration file.

```
vi /etc/supervisor/conf.d/my_project.conf
```
Paste the following text into the file and change it if necessary.

```
[program:fastapi-app]
command=/home/fastapi-user/my_fastapi_project/gunicorn_start
user=fastapi-user
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/fastapi-user/my_fastapi_project/logs/gunicorn-error.log
```
Use Supervisor Control to update and start the fastapi-app (gunicorn_start).

```
supervisorctl reread
supervisorctl update
```
Check the status (or stop) the app.

```
supervisorctl status fastapi-app

supervisorctl stop fastapi-app
```

## 6. Nginx
The basic Nginx settings.

```
vi /etc/nginx/nginx.conf
```

```
worker_processes 1;

user nobody nogroup;
# 'user nobody nobody;' for systems with 'nobody' as a group instead
error_log  /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;
include /etc/nginx/modules-enabled/*.conf;

events {
  worker_connections 1024; # increase if you have lots of clients
  accept_mutex off; # set to 'on' if nginx worker_processes > 1
  # 'use epoll;' to enable for Linux 2.6+
  # 'use kqueue;' to enable for FreeBSD, OSX
}

http {
        include /etc/nginx/mime.types;
        # fallback in case we can't determine a type
        default_type application/octet-stream;
        access_log /var/log/nginx/access.log combined;
        sendfile on;

        include /etc/nginx/conf.d/*.conf;
        include /etc/nginx/sites-enabled/*;
}
```

Tell Nginx to listen on the default port 80. Let’s also tell it to use this block for requests for our server’s domain name or IP address. Replace the placeholder SERVER-NAME-OR-IP with the correct value.

```
vi /etc/nginx/sites-available/my_fastapi_project
```

```
server {
    listen 80;
    client_max_body_size 1G;

    # set the correct host(s) for your site
    server_name SERVER-NAME-OR-IP;

    location / {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Host $host;
        proxy_redirect off;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

Disable the Nginx `default` server block.

```
rm -rf /etc/nginx/sites-enabled/default
```

Enable the Nginx `my_fastapi_project` server block.

```
ln -s /etc/nginx/sites-available/my_fastapi_project /etc/nginx/sites-enabled/
```

Restart the Nginx process to read the new configuration.

```
systemctl restart nginx
```

Test locally and/or from the Moodle server using the above curl command.

```
curl -F 'file=@/home/fastapi-user/sample1.docx' http://SERVER-NAME-OR-IP/upload
```

**Attention! Set the server's firewall to only allow requests from the Moodle server on port 80.**

## 7. Privacy
To ensure data protection, a cron job can be created that deletes the converted files after a certain time.

Create a shell script.

```
vi /root/delete_files_fastapi.sh
```

```
#!/bin/bash

uploads_dir=/home/fastapi-user/my_fastapi_project/tmp
retention_time=10
find ${uploads_dir} -type f -mmin +${retention_time} -exec rm {} \;
```

Add an entry in the Contab.

```
crontab -e
```

```
* * * * * /bin/sh /root/delete_files_fastapi.sh
```

## Useful links

* [Deploy a FastAPI app with NGINX and Gunicorn (update 2025)](https://medium.com/@kevinzeladacl/deploy-a-fastapi-app-with-nginx-and-gunicorn-b66ac14cdf5a)
* [Setting Up a FastAPI Project with NGINX Reverse Proxy on Ubuntu](https://dev.to/udara_dananjaya/setting-up-a-fastapi-project-with-nginx-reverse-proxy-on-ubuntu-883)
* [Preparing FastAPI for Production: A Comprehensive Guide](https://medium.com/@ramanbazhanau/preparing-fastapi-for-production-a-comprehensive-guide-d167e693aa2b)
* [Converting DOCX to PDF using Python](https://michalzalecki.com/converting-docx-to-pdf-using-python/)
