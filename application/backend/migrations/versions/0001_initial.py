"""Initial domain schema and database enforcement of immutable training evidence."""
from alembic import op
from migrations.schema_v1 import create_schema

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create the initial schema and DB guards; fail transactionally if DDL cannot be applied."""
    bind = op.get_bind()
    create_schema()
    immutable = ("quiz_items", "scenario_validations", "attempt_events", "grade_reviews", "audit_events", "components", "machines")
    if bind.dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION ff_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Immutable training record'; END; $$""")
        for table in immutable:
            op.execute(f"CREATE TRIGGER ff_guard BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION ff_immutable()")
        op.execute("""CREATE FUNCTION ff_scenario_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Use retirement'; END IF;
          IF NEW.payload::text <> OLD.payload::text OR NEW.source_case_ids::text <> OLD.source_case_ids::text
             OR NEW.source_manifest::text <> OLD.source_manifest::text OR NEW.content_hash <> OLD.content_hash
             OR NEW.generator_version <> OLD.generator_version OR NEW.machine_id <> OLD.machine_id
             OR NEW.difficulty <> OLD.difficulty THEN RAISE EXCEPTION 'Create a new scenario version'; END IF;
          RETURN NEW; END; $$""")
        op.execute("CREATE TRIGGER ff_scenario_guard BEFORE UPDATE OR DELETE ON scenario_templates FOR EACH ROW EXECUTE FUNCTION ff_scenario_guard()")
        op.execute("ALTER TABLE scenario_templates ADD CONSTRAINT ff_nonempty_cases CHECK (json_array_length(source_case_ids) > 0)")
    else:
        for table in immutable:
            for action in ("UPDATE", "DELETE"):
                op.execute(f"CREATE TRIGGER ff_{table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Immutable training record'); END")
        op.execute("""CREATE TRIGGER ff_scenario_delete BEFORE DELETE ON scenario_templates BEGIN SELECT RAISE(ABORT, 'Use retirement'); END""")
        op.execute("""CREATE TRIGGER ff_scenario_update BEFORE UPDATE OF payload, source_case_ids, source_manifest, content_hash,
          generator_version, machine_id, difficulty ON scenario_templates BEGIN SELECT RAISE(ABORT, 'Create a new scenario version'); END""")
        op.execute("""CREATE TRIGGER ff_nonempty_cases BEFORE INSERT ON scenario_templates
          WHEN json_array_length(NEW.source_case_ids) = 0 BEGIN SELECT RAISE(ABORT, 'Source case IDs required'); END""")


def downgrade():
    """Refuse destructive schema rollback; restore a verified backup through the operations runbook."""
    raise RuntimeError("Destructive downgrade disabled; preserve training history and restore a verified backup.")
