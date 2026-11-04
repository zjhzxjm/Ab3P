"""Release bundle contract; writes only below an explicit isolated root."""
import argparse,hashlib,json,pathlib,shutil,subprocess,tarfile

def verify(archive,dest):
 with tarfile.open(archive) as t:
  names=set()
  for m in t.getmembers():
   p=pathlib.PurePosixPath(m.name)
   if p.is_absolute() or '..' in p.parts or m.issym() or m.islnk() or not (m.isfile() or m.isdir()): raise ValueError('Unsafe member')
   if m.name in names: raise ValueError('Duplicate member')
   names.add(m.name)
  t.extractall(dest)
 info=json.loads((dest/'build-info.json').read_text())
 assert info['bundle_schema']==info['driver_schema']==1
 assert info['platform']=='linux-x86_64' and info['bits']==64 and info['byteorder']=='little'
 assert len(info['ab3p_sha'])==len(info['ncbitextlib_sha'])==40
 assert not list(dest.rglob('path_Ab3P'))
 assert (dest/'NOTICE').stat().st_size and (dest/'bin/identify_abbr_jsonl').is_file()
 actual={str(p.relative_to(dest)) for p in dest.rglob('*') if p.is_file()}-{'build-info.json'}
 assert actual==set(info['members'])
 assert any(x.startswith('WordData/') for x in actual)
 for name,digest in info['members'].items(): assert hashlib.sha256((dest/name).read_bytes()).hexdigest()==digest
 return info

def main():
 p=argparse.ArgumentParser();p.add_argument('--archive',required=True);p.add_argument('--run-root',required=True);a=p.parse_args()
 root=pathlib.Path(a.run_root).resolve();root.mkdir(parents=True,exist_ok=False)
 bundle=root/'relocated bundle';bundle.mkdir();info=verify(a.archive,bundle)
 work=root/'different cwd';work.mkdir();(work/'path_Ab3P').write_text(str(bundle/'WordData')+'/\n')
 cases={'defined':'Tumor necrosis factor (TNF).\nNo definitions.\n\n','unicode':'β tumor necrosis factor (TNF).\n','empty':''}
 for name,text in cases.items():
  source=work/(name+'.txt');source.write_text(text)
  r=subprocess.run([str(bundle/'bin/identify_abbr_jsonl'),str(source)],cwd=work,capture_output=True);assert r.returncode==0,r.stderr
  rows=[json.loads(x) for x in r.stdout.splitlines()];assert len(rows)==text.count('\n')
  assert all(v['schema_version']==1 and v['line_index']==i for i,v in enumerate(rows))
  if name=='defined':assert rows[0]['records'] and rows[1]['records']==rows[2]['records']==[]
  if name=='empty':assert r.stdout==b''
 for text in [b'\0TNF',None]:
  source=work/'failure';
  if text is not None:source.write_bytes(text)
  elif source.exists():source.unlink()
  assert subprocess.run([str(bundle/'bin/identify_abbr_jsonl'),str(source)],cwd=work,capture_output=True).returncode!=0
 report={'status':'passed','archive_sha256':hashlib.sha256(pathlib.Path(a.archive).read_bytes()).hexdigest(),'build_info':info,'checks':['members','platform','relocation','different_cwd','jsonl','empty','unicode','nonzero']}
 (root/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':'passed','archive_sha256':report['archive_sha256']}))
if __name__=='__main__':main()
