import os, sys
from pathlib import Path
from subprocess import TimeoutExpired
from fastapi import FastAPI, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse

from config import config
from common.convert import LibreOfficeError, convert_to
from werkzeug.utils import secure_filename

import logging

app = FastAPI()

logger = logging.getLogger('uvicorn.error')

@app.get('/', response_class=PlainTextResponse)
async def read_root():
    return 'OK'

@app.post('/upload')
async def upload_file(file: UploadFile):

    filename_sec = secure_filename(file.filename)
    file_directory = os.path.join(config['uploads_dir'], 'source')
    file_location = f"{file_directory}/{filename_sec}"

    os.makedirs(file_directory, exist_ok=True)

    web_file_url_source = os.path.join('/upload', 'source', filename_sec)
    path_object = Path(filename_sec)
    new_filename = path_object.with_suffix('.' + 'pdf')
    web_file_url_result = os.path.join('/upload', 'pdf', new_filename)

    with open(file_location, 'wb') as buffer:
        buffer.write(await file.read())

    try:
        result = convert_to(os.path.join(config['uploads_dir'], 'pdf'), file_location, timeout=15)
    except LibreOfficeError:
        logger.debug('Info - doc-conv-failed LibreOfficeError ' + str(filename_sec))
        return {'result': {'source': web_file_url_source, 'doc-conv-failed': 'LibreOfficeError'}}
    except TimeoutExpired:
        logger.debug('Info - doc-conv-failed TimeoutExpired ' + str(filename_sec))
        return {'result': {'source': web_file_url_source, 'doc-conv-failed': 'TimeoutExpired'}}
    except:
        logger.debug('Info - doc-conv-failed OtherError ' + str(filename_sec))
        return {'result': {'source': web_file_url_source, 'doc-conv-failed': 'OtherError'}}

    logger.debug('Info - all ok ' + str(filename_sec) + ' ' + str(new_filename))
    return {'result': {'source': web_file_url_source, 'pdf': web_file_url_result}}

@app.get('/upload/pdf/{filename}')
async def download(filename: str):
    file_directory = os.path.join(config['uploads_dir'], 'pdf')
    file_location = f"{file_directory}/{filename}"
    return FileResponse(path=file_location, filename=filename, media_type="application/pdf")

