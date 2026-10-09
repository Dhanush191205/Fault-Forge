"""Preserve source versions, completed assessments and referenced history at the database boundary."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    """Add non-destructive history guards; reject source replacement and reassignment of recorded grades."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION ff_source_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Preserve source version'; END IF;
          IF NEW.content::text <> OLD.content::text OR NEW.checksum <> OLD.checksum OR NEW.machine_id <> OLD.machine_id
             OR NEW.kind <> OLD.kind OR NEW.synthetic <> OLD.synthetic OR NEW.locator <> OLD.locator
             OR NEW.title <> OLD.title THEN RAISE EXCEPTION 'Create a new source version'; END IF;
          RETURN NEW; END; $$""")
        op.execute("CREATE TRIGGER ff_source_guard BEFORE UPDATE OR DELETE ON sources FOR EACH ROW EXECUTE FUNCTION ff_source_guard()")
        op.execute("""CREATE FUNCTION ff_attempt_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Preserve attempt history'; END IF;
          IF OLD.submission IS NOT NULL AND OLD.submission::text <> 'null' AND
             (NEW.submission::text IS DISTINCT FROM OLD.submission::text OR NEW.result::text IS DISTINCT FROM OLD.result::text
              OR NEW.user_id <> OLD.user_id OR NEW.scenario_id <> OLD.scenario_id OR NEW.submit_key IS DISTINCT FROM OLD.submit_key)
          THEN RAISE EXCEPTION 'Completed assessment is immutable'; END IF;
          RETURN NEW; END; $$""")
        op.execute("CREATE TRIGGER ff_attempt_guard BEFORE UPDATE OR DELETE ON attempts FOR EACH ROW EXECUTE FUNCTION ff_attempt_guard()")
    else:
        op.execute("""CREATE TRIGGER ff_source_delete BEFORE DELETE ON sources BEGIN SELECT RAISE(ABORT, 'Preserve source version'); END""")
        op.execute("""CREATE TRIGGER ff_source_update BEFORE UPDATE OF content,checksum,machine_id,kind,synthetic,locator,title ON sources
          BEGIN SELECT RAISE(ABORT, 'Create a new source version'); END""")
        op.execute("""CREATE TRIGGER ff_attempt_delete BEFORE DELETE ON attempts BEGIN SELECT RAISE(ABORT, 'Preserve attempt history'); END""")
        op.execute("""CREATE TRIGGER ff_attempt_update BEFORE UPDATE OF submission,result,user_id,scenario_id,submit_key ON attempts
          WHEN OLD.submission IS NOT NULL AND OLD.submission != 'null'
          BEGIN SELECT RAISE(ABORT, 'Completed assessment is immutable'); END""")


def downgrade():
    """Refuse removal of audit guarantees through routine rollback."""
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup instead.")
