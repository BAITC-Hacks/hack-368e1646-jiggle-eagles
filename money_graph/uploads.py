"""Bounded local upload parsing and safe, actionable failure categories."""
from email import policy
from email.parser import BytesParser
import errno

from .pipeline import ValidationError

MAX_UPLOAD_BYTES = 64 * 1024 * 1024
INPUT_NAMES = ('nodes', 'edges', 'transactions')
RECEIVE_TIMEOUT_SECONDS = 30


def parse_upload(content_type: str, body: bytes) -> dict[str, bytes]:
    """Preserve binary file bytes; reject incomplete or ambiguous multipart data."""
    if len(body) > MAX_UPLOAD_BYTES:
        raise ValidationError('error.uploadLimit')
    try:
        if '\r' in content_type or '\n' in content_type:
            raise ValueError('Invalid content type')
        envelope = f'Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n'.encode('ascii')
        message = BytesParser(policy=policy.default).parsebytes(envelope + body)
    except (ValueError, TypeError) as error:
        raise ValidationError('error.multipart') from error
    if message.get_content_type() != 'multipart/form-data' or not message.is_multipart() or message.defects:
        raise ValidationError('error.multipart')
    files = {}
    for part in message.iter_parts():
        name = part.get_param('name', header='content-disposition')
        if (part.defects or part.is_multipart() or part.get_content_disposition() != 'form-data'
                or len(part.get_all('Content-Disposition', [])) != 1
                or part.get('Content-Transfer-Encoding') is not None
                or part.get('Content-Encoding') is not None
                or name not in INPUT_NAMES or name in files or part.get_filename() != f'{name}.parquet'):
            raise ValidationError('error.exactFiles')
        payload = part.get_payload(decode=True)
        if not payload:
            raise ValidationError('error.emptyFile', name=name)
        files[name] = payload
    if set(files) != set(INPUT_NAMES):
        raise ValidationError('error.threeFiles')
    return files


def read_upload(stream, connection, content_type: str, length: int) -> dict[str, bytes]:
    """Read a bounded request, reporting disconnect and timeout separately."""
    if not 0 < length <= MAX_UPLOAD_BYTES:
        raise ValidationError('error.uploadLimit')
    try:
        connection.settimeout(RECEIVE_TIMEOUT_SECONDS)
        body = stream.read(length)
    except TimeoutError as error:
        raise ValidationError('error.uploadTimeout') from error
    except OSError as error:
        raise ValidationError('error.interrupted') from error
    if len(body) != length:
        raise ValidationError('error.interrupted')
    return parse_upload(content_type, body)


def analysis_failure(error: Exception) -> ValidationError:
    """Do not expose filesystem paths or raw parser/runtime exception text."""
    if isinstance(error, ValidationError):
        return error
    if isinstance(error, OSError):
        if error.errno in {errno.ENOSPC, errno.EDQUOT}:
            return ValidationError('error.storageFull')
        if error.errno in {errno.EACCES, errno.EPERM, errno.EROFS}:
            return ValidationError('error.storagePermission')
    return ValidationError('error.analysis')
