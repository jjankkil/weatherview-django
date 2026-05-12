_FILTERED = {"Test", "LA", "TSA", "TEST", "Meteo", "LAMID", "OptX"}


def ok_to_add_station(raw_name: str) -> bool:
    if not raw_name:
        return False
    for token in _FILTERED:
        if token in raw_name:
            return False
    return True
