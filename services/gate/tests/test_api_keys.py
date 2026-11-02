import uuid

from sense_gate.models.tenant import ApiKey


def test_generate_stores_only_hash():
    row, raw = ApiKey.generate(uuid.uuid4(), name="k", test=True)
    assert raw.startswith("sk_test_")
    assert row.key_hash == ApiKey.hash_key(raw) and len(row.key_hash) == 64
    assert row.key_prefix == raw[:12]
    assert raw not in repr(row)
    assert not hasattr(row, "key")


def test_keys_are_unique_and_hash_differs():
    (a, ra), (b, rb) = ApiKey.generate(uuid.uuid4()), ApiKey.generate(uuid.uuid4())
    assert ra != rb and a.key_hash != b.key_hash
