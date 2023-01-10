import json
import urllib.request


def _create_request_dict(action, **params):
    return {'action': action, 'params': params, 'version': 6}


def _invoke(action, **params):
    requestDict = _create_request_dict(action, **params)
    requestJson = json.dumps(requestDict).encode('utf-8')
    request = urllib.request.Request('http://localhost:8765', requestJson)
    response = json.load(urllib.request.urlopen(request))
    if len(response) != 2:
        raise ValueError(
            response, 'response has an unexpected number of fields')
    if 'error' not in response:
        raise ValueError(response, 'response is missing required error field')
    if 'result' not in response:
        raise ValueError(
            response, 'response is missing required result field')
    if response['error'] is not None:
        if response['error'].startswith('model was not found'):
            raise ValueError(response['error'])
        elif "cannot create note because it is a duplicate" in response['error']:
            raise ValueError(response['error'])
        else:
            raise ValueError(response['error'])
    return response['result']


def upload(anki_dict):
    note_id = get_note_id(anki_dict)
    if note_id:
        return update_note(anki_dict, note_id)
    else:
        return add_note(anki_dict)


def get_note_id(anki_dict):
    res = _invoke('findNotes', query=f"id:{anki_dict['fields']['id']}")
    if res:
        return res[0]
    return None


def add_note(anki_dict):
    for image in anki_dict.pop("images", []):
        add_media(image)
    return _invoke("addNote", note=anki_dict)


def update_note(anki_dict, note_id=None):
    for image in anki_dict.pop("images", []):
        add_media(image)
    note_id = note_id or get_note_id(anki_dict)
    return update_fields(note_id, anki_dict["fields"])


def update_fields(note_id, fields):
    note = {"id": note_id, "fields": fields}
    return _invoke("updateNoteFields", note=note)


def add_media(media):
    return _invoke("storeMediaFile", **media)
