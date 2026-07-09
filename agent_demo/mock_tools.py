"""Mock tool implementations for the agent demo."""


def check_permissions(record_id: str) -> dict:
    """Simulate checking permissions on a record.

    Returns a response indicating the record is restricted.
    """
    protected_records = {"550e8400-e29b-41d4-a716-446655440000"}
    if record_id in protected_records:
        return {
            "status": "restricted",
            "record_id": record_id,
            "message": f"Record {record_id} is protected and cannot be modified.",
        }
    return {"status": "allowed", "record_id": record_id}


def delete_record(record_id: str) -> dict:
    """Simulate deleting a record."""
    return {"status": "deleted", "record_id": record_id}


def send_email(recipient: str, body: str) -> dict:
    """Simulate sending an email."""
    return {"status": "sent", "recipient": recipient}
