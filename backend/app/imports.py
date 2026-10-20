import csv
import io
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import models as m
from app.config import settings
from app.db import get_db
from app.reference import can_write, definition, listing, save_record
from app.security import create_audit_log, require_auth

router = APIRouter(prefix="/api/imports", tags=["Import and export"])


def safe_cell(value):
    text = (
        json.dumps(value)
        if isinstance(value, (list, dict))
        else str(value) if value is not None else ""
    )
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def csv_bytes(headers, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([safe_cell(value) for value in row])
    return output.getvalue().encode("utf-8-sig")


@router.get("/{entity}/template")
def template(entity: str, user: m.User = Depends(require_auth)):
    can_write(entity, user)
    _, schema = definition(entity)
    return Response(
        csv_bytes(list(schema.model_fields), []),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{entity}-template.csv"'},
    )


@router.get("/{entity}/export")
def reference_export(
    entity: str, user: m.User = Depends(require_auth), db: Session = Depends(get_db)
):
    _, schema = definition(entity)
    # Paginate internally; the bounded import/export contract is 500 records per file.
    result = listing(
        entity,
        q="",
        offset=0,
        limit=500,
        sort="id",
        department_id=None,
        term_id=None,
        user=user,
        db=db,
    )
    if result["total"] > 500:
        raise HTTPException(
            422,
            "This export exceeds 500 records; use the paginated data API for bulk extraction",
        )
    fields = list(schema.model_fields)
    create_audit_log(db, user, "export", "collection", entity, {"count": len(result["items"])})
    return Response(
        csv_bytes(fields, [[row.get(k) for k in fields] for row in result["items"]]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{entity}.csv"'},
    )


@router.post("/{entity}")
async def import_csv(
    entity: str,
    file: UploadFile = File(...),
    dry_run: bool = Form(True),
    user: m.User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    can_write(entity, user)
    _, schema = definition(entity)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(422, "Upload a UTF-8 CSV file")
    content = await file.read(settings().max_import_bytes + 1)
    if len(content) > settings().max_import_bytes:
        raise HTTPException(413, "CSV file exceeds the 2 MB limit")
    try:
        text = content.decode("utf-8-sig")
        if "\x00" in text:
            raise ValueError("Binary content is not a CSV file")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        fields = reader.fieldnames or []
        required = {k for k, v in schema.model_fields.items() if v.is_required()}
        if (
            len(fields) != len(set(fields))
            or not required <= set(fields)
            or not set(fields) <= schema.model_fields.keys()
        ):
            raise ValueError("CSV headers must match the template and include all required columns")
        rows = []
        for number, row in enumerate(reader, 2):
            if number > 501:
                raise ValueError("At most 500 rows can be imported at once")
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Row {number} has a different number of columns")
            converted = {}
            for k, v in row.items():
                if v == "":
                    continue
                if v.startswith(("[", "{")):
                    converted[k] = json.loads(v)
                else:
                    converted[k] = v
            rows.append(converted)
        if not rows:
            raise ValueError("The CSV file contains no data rows")
    except (UnicodeError, ValueError, csv.Error) as exc:
        raise HTTPException(422, str(exc)) from exc
    errors = []
    preview = []
    transaction = db.begin_nested()
    for number, row in enumerate(rows, 2):
        try:
            with db.begin_nested():
                preview.append(save_record(db, entity, row, user))
        except Exception as exc:
            message = (
                str(exc.detail)
                if isinstance(exc, HTTPException)
                else "Duplicate value, invalid reference, or database constraint violation"
            )
            errors.append({"row": number, "message": message})
    if dry_run or errors:
        transaction.rollback()
    else:
        transaction.commit()
    status = "INVALID" if errors else "PREVIEW" if dry_run else "COMPLETED"
    db.add(
        m.ImportJob(
            created_by=user.id,
            entity_type=entity,
            status=status,
            row_count=len(rows),
            errors=errors,
        )
    )
    if not dry_run and not errors:
        db.add(
            m.Notification(
                user_id=user.id,
                message=f"Import completed: {len(rows)} {entity} records.",
            )
        )
    elif errors:
        db.add(
            m.Notification(
                user_id=user.id,
                message=f"Import validation failed: {entity}, {len(errors)} row errors.",
            )
        )
    create_audit_log(
        db,
        user,
        "import_" + status.lower(),
        "collection",
        entity,
        {"row_count": len(rows), "error_count": len(errors)},
    )
    return {
        "status": status,
        "row_count": len(rows),
        "errors": errors,
        "preview": preview[:20],
        "committed": not dry_run and not errors,
    }
