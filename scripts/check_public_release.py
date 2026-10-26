"""Check tracked publication boundaries and local Markdown links without raw inputs."""
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote,urlsplit

ROOT=Path(__file__).resolve().parents[1]
PRIVATE_PREFIXES=('analysis/','document/','data/raw/','data/policy/','data/reference/',
                  'data/external/','repro/m3/data/','repro/m3/models/',
                  'repro/m3/results/','repro/m3/report/','reproduction_runs/')
PRIVATE_SUFFIXES={'.joblib','.parquet','.duckdb','.db','.sqlite','.sqlite3','.pem','.key','.p12','.pfx'}


def main():
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf-8').split('\0')
    errors=[]
    for name in filter(None,tracked):
        path=ROOT/name
        if not path.exists():
            errors.append(f'Tracked file is missing: {name}')
            continue
        if (name.startswith(PRIVATE_PREFIXES) or Path(name).suffix.lower() in PRIVATE_SUFFIXES
                or Path(name).name.startswith('.env') and Path(name).name!='.env.example'):
            errors.append(f'Private or generated file is tracked: {name}')
        if name.endswith('.md'):
            for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
                target=link.strip('<>')
                parsed=urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                destination=(path.parent/unquote(parsed.path)).resolve()
                if not destination.is_relative_to(ROOT) or not destination.exists():
                    errors.append(f'Broken local link in {name}: {target}')
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'Publication boundaries and local Markdown links passed ({len(list(filter(None,tracked)))} tracked files).')


if __name__=='__main__':
    main()
