from app.redact import redact_credentials, redact_object


def test_redacts_password_value_after_keyword():
    assert "пароль REDACTED" in redact_credentials("логин user\nпароль RaPgzw74gnliZ9")
    assert "RaPgzw74gnliZ9" not in redact_credentials("пароль RaPgzw74gnliZ9")


def test_redacts_inline_login_password_pair():
    out = redact_credentials("**логин** 9P5bRTR4Dc, **пароль** TfriAgZkj5")
    assert "9P5bRTR4Dc" not in out
    assert "TfriAgZkj5" not in out
    assert "REDACTED" in out


def test_redacts_mailto_link():
    out = redact_credentials("логин [tech@profitreid.com](mailto:tech@profitreid.com)")
    assert "tech@profitreid.com" not in out
    assert "REDACTED" in out


def test_redacts_html_mailto():
    out = redact_credentials('<a href="mailto:tech@profitreid.com">tech@profitreid.com</a>')
    assert "tech@profitreid.com" not in out
    assert "********" in out
    assert "REDACTED" in out


def test_not_redacts_instruction_words():
    out = redact_credentials("**Логин:** Используйте ваш стандартный логин (как на сервере)")
    assert out == "**Логин:** Используйте ваш стандартный логин (как на сервере)"


def test_not_redacts_empty_label():
    out = redact_credentials("Логин для входа:\n\n* Пароль для входа:")
    assert out == "Логин для входа:\n\n* Пароль для входа:"


def test_redact_object_content():
    obj = {"name": "Статья", "content": "пароль abcD1234 XYZ"}
    redact_object(obj)
    assert obj["name"] == "Статья"
    assert "abcD1234" not in obj["content"]
    assert "REDACTED" in obj["content"]


def test_redact_object_with_keys():
    obj = {"title": "secretValue9", "content": "логин u1"}
    redact_object(obj, key_names=frozenset({"content"}))
    assert obj["title"] == "secretValue9"
    assert obj["content"] == "логин REDACTED"


def test_redact_is_idempotent():
    once = redact_credentials("пароль Qwerty12345")
    assert redact_credentials(once) == once