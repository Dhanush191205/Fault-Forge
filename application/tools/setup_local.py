"""Initialize local environment with unique random credentials; never overwrite existing secrets."""
import secrets
from pathlib import Path


def main():
    """Create .env and private access notes if absent; refuse to rotate credentials implicitly."""
    root = Path(__file__).resolve().parents[1]
    env_file = root / ".env"
    if env_file.exists():
        print("Existing .env preserved. Use its configured accounts.")
        return
    values = {"INSTRUCTOR_PASSWORD": secrets.token_urlsafe(24), "TRAINEE_PASSWORD": secrets.token_urlsafe(24),
              "POSTGRES_PASSWORD": secrets.token_urlsafe(24)}
    lines = (root / ".env.example").read_text(encoding="utf-8").splitlines()
    output = []
    for line in lines:
        key = line.split("=", 1)[0]
        output.append(f"{key}={values[key]}" if key in values else line)
    env_file.write_text("\n".join(output) + "\n", encoding="utf-8")
    (root / "local-access.txt").write_text(
        "Fault Forge — local demo access (private, not for source control)\n\n"
        "Open http://localhost:5173\n\n"
        f"Instructor: instructor@faultforge.local\nPassword: {values['INSTRUCTOR_PASSWORD']}\n\n"
        f"Trainee: trainee@faultforge.local\nPassword: {values['TRAINEE_PASSWORD']}\n\n"
        "Review and publish a draft from Instructor studio before starting a trainee session.\n", encoding="utf-8")
    print("Created .env and local-access.txt with unique random credentials.")


if __name__ == "__main__":
    main()
