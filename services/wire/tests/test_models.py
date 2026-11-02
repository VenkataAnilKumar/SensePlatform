from sqlalchemy.orm import configure_mappers


def test_mappers_configure():
    """Regression: Message.replies/parent was an invalid self-referential mapping."""
    import sense_wire.models.channel  # noqa: F401
    import sense_wire.models.message  # noqa: F401

    configure_mappers()


def test_message_parent_replies_are_inverse():
    from sense_wire.models.message import Message

    assert Message.parent.property.remote_side
    assert Message.replies.property.back_populates == "parent"
