"""Constants for PrintAssist integration."""
from typing import Final

DOMAIN: Final = "printassist"
NAME: Final = "PrintAssist"

STORAGE_KEY: Final = f"{DOMAIN}.storage"
STORAGE_VERSION: Final = 1

CONF_PRINTER_ENTITY: Final = "printer_entity"

ATTR_PROJECT_ID: Final = "project_id"
ATTR_PROJECT_NAME: Final = "name"
ATTR_PLATE_ID: Final = "plate_id"
ATTR_JOB_ID: Final = "job_id"
ATTR_QUANTITY: Final = "quantity"
ATTR_PRIORITY: Final = "priority"
ATTR_NOTES: Final = "notes"
ATTR_FAILURE_REASON: Final = "failure_reason"
ATTR_FILENAME: Final = "filename"
ATTR_FILE_CONTENT: Final = "file_content"
ATTR_START: Final = "start"
ATTR_END: Final = "end"
ATTR_WINDOW_ID: Final = "window_id"

JOB_STATUS_QUEUED: Final = "queued"
JOB_STATUS_PRINTING: Final = "printing"
JOB_STATUS_COMPLETED: Final = "completed"
JOB_STATUS_FAILED: Final = "failed"

THUMBNAIL_DIR: Final = "www/printassist/thumbnails"
GCODE_DIR: Final = ".storage/printassist/gcode"

SERVICE_CREATE_PROJECT: Final = "create_project"
SERVICE_DELETE_PROJECT: Final = "delete_project"
SERVICE_UPLOAD_3MF: Final = "upload_3mf"
SERVICE_DELETE_PLATE: Final = "delete_plate"
SERVICE_SET_PLATE_PRIORITY: Final = "set_plate_priority"
SERVICE_SET_QUANTITY: Final = "set_quantity"
SERVICE_START_JOB: Final = "start_job"
SERVICE_COMPLETE_JOB: Final = "complete_job"
SERVICE_FAIL_JOB: Final = "fail_job"
SERVICE_ADD_UNAVAILABILITY: Final = "add_unavailability"
SERVICE_REMOVE_UNAVAILABILITY: Final = "remove_unavailability"
