# Frozen contracts

Causal chain:

Sport → Event environment → Discrete regime → Team opportunity pool → Role → Player opportunity → Conditional efficiency → Primitive stats → Derived stats → MarketDefinition → line/side comparison → Administrative → Economic.

Persistent objects carry schema_version, created_at_utc, learning_revision, source_hashes, content_hash.

`created_at_utc` is excluded from semantic content hashes.

Composites (PRA, pass+rush, H+R+RBI, fantasy) are functions of one PrimitiveStatLedger.
