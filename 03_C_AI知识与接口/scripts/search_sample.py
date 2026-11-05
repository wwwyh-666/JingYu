import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.repository import Repository
p=argparse.ArgumentParser(description='仅本地候选检索，不调用模型')
p.add_argument('query');p.add_argument('--spot',default='TT');p.add_argument('--include-unreviewed',action='store_true')
a=p.parse_args()
print(json.dumps({'mode':'local_keyword_retrieval','model_called':False,
 'include_unreviewed':a.include_unreviewed,'items':[f.model_dump() for f in Repository().search(
 a.spot,a.query,include_unreviewed=a.include_unreviewed)]},ensure_ascii=False,indent=2))
