from sqlalchemy import DateTime
from sqlalchemy.dialects import oracle

UTCDateTime = DateTime(timezone=True).with_variant(
    oracle.TIMESTAMP(timezone=True),
    "oracle",
)
