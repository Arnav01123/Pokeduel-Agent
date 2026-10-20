from paths import ROOT
YOURS = (ROOT / 'agent' / 'team.txt').read_text()                    # Focus Sash Tyranitar
OVERNIGHT = (ROOT / 'baselines' / 'overnight_team.txt').read_text()   # Assault Vest Tyranitar
assert 'Focus Sash' in YOURS and 'Assault Vest' in OVERNIGHT
