import subprocess
from pathlib import Path
path = Path('git_commit_output.txt')
try:
    result = subprocess.run(
        ['git', 'add', '.github/rules/operation/posture_definition_criteria.json', 'src/core/judgment_engine.py'],
        capture_output=True,
        text=True,
        check=False,
    )
    result2 = subprocess.run(
        ['git', 'commit', '-m', "Merge branch 'eunsu' into main"],
        capture_output=True,
        text=True,
        check=False,
    )
    path.write_text('ADD OUT:\n' + result.stdout + result.stderr + '\nCOMMIT OUT:\n' + result2.stdout + result2.stderr, encoding='utf-8')
except Exception as e:
    path.write_text('EXCEPTION:\n' + repr(e), encoding='utf-8')
