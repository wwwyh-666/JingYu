import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.repository import Repository
p=argparse.ArgumentParser();p.add_argument('query');p.add_argument('--include-unreviewed',action='store_true');a=p.parse_args()
print(json.dumps({'model_called':False,'results':Repository().retrieve_with_claims('TT',a.query,include_unreviewed=a.include_unreviewed)},ensure_ascii=False,indent=2))
