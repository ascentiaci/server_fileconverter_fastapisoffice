
import os

config = {
    "uploads_dir": os.environ.get("UPLOADS_DIR", "/home/fastapi-user/my_fastapi_project/tmp")
}
