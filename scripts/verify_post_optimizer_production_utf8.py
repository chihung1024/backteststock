from __future__ import annotations

import requests

_original_get = requests.get


def _utf8_get(*args, **kwargs):
    response = _original_get(*args, **kwargs)
    response.encoding = "utf-8"
    return response


requests.get = _utf8_get

from verify_post_optimizer_production import main  # noqa: E402


if __name__ == "__main__":
    main()
