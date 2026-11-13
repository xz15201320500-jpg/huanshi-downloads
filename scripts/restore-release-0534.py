import hashlib,json,os,subprocess
from pathlib import Path
m=json.loads(Path('transfer-manifest.json').read_text());repo=os.environ['GITHUB_REPOSITORY'];incoming=Path('input');output=Path('restored');output.mkdir(exist_ok=True)
assert m['targetTag']=='v0.5.34' and m['baselineTag']=='v0.5.33' and len(m['files'])==5
assert json.loads((incoming/'manifest.json').read_text())==m

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def run(*args):subprocess.run(args,check=True)
restored=[];pending=[]
remote=[]
if not os.environ.get('VERIFY_ONLY'):
 state=json.loads(subprocess.check_output(['gh','release','view',m['targetTag'],'--repo',repo,'--json','assets,isDraft']))
 assert state['isDraft'] is True
 remote=state['assets']
for f in m['files']:
 assert Path(f['name']).name==f['name'] and f['name'].startswith('Huanshi-0.5.34-')
 assert Path(f['baselineName']).name==f['baselineName'] and f['baselineName'].startswith('Huanshi-0.5.33-')
 if any(a['name']==f['name'] and a['size']==f['size'] and a.get('digest')=='sha256:'+f['sha256'] for a in remote):
  print('ALREADY VERIFIED',f['name'],flush=True);continue
 missing=[p['name'] for p in f['parts'] if not (incoming/p['name']).is_file()]
 if missing and os.environ.get('ALLOW_PARTIAL'):
  pending.append(f['name']);continue
 assert not missing,missing
 local=os.environ.get('LOCAL_BASELINES');base=(Path(local) if local else Path('baseline'))/f['baselineName']
 if not local:
  base.parent.mkdir(exist_ok=True);run('gh','release','download',m['baselineTag'],'--repo',repo,'--pattern',f['baselineName'],'--dir',str(base.parent),'--clobber')
 assert sha(base)==f['baselineSha256']
 patch=Path('restore.patch.zst')
 with patch.open('wb') as out:
  for p in f['parts']:
   assert Path(p['name']).name==p['name']
   part=incoming/p['name'];assert part.stat().st_size==p['size'] and sha(part)==p['sha256']
   with part.open('rb') as src:
    for b in iter(lambda:src.read(1024*1024),b''):out.write(b)
 assert sha(patch)==f['patchSha256']
 target=output/f['name'];run(os.environ.get('ZSTD','zstd'),'-d','-M2048MB','--patch-from='+str(base),str(patch),'-o',str(target),'-f')
 assert target.stat().st_size==f['size'] and sha(target)==f['sha256']
 print('VERIFIED',f['name'],f['sha256'],flush=True);restored.append(f)
 patch.unlink()
 if not local:base.unlink()
if not os.environ.get('VERIFY_ONLY'):
 assert json.loads(subprocess.check_output(['gh','release','view',m['targetTag'],'--repo',repo,'--json','isDraft']))['isDraft'] is True
 for f in restored:run('gh','release','upload',m['targetTag'],'--repo',repo,'--clobber',str(output/f['name']))
print(json.dumps({'restored':len(restored),'pending':pending}),flush=True)
