#!/usr/bin/env bash
set -euo pipefail
# Release-only builder. All writes are below a new, explicit isolated directory.
: "${RELEASE_ROOT:?}" "${AB3P_SOURCE:?}" "${NCBI_SOURCE:?}"
mkdir "$RELEASE_ROOT"
export RELEASE_ROOT AB3P_SOURCE NCBI_SOURCE
python3 - <<'BUILD'
import hashlib,json,os,pathlib,shutil,subprocess,tarfile
root=pathlib.Path(os.environ['RELEASE_ROOT']).resolve()
def call(args,cwd=None): return subprocess.check_output(args,cwd=cwd,stderr=subprocess.STDOUT).decode()
def export(repo,dest,ref='HEAD'):
 dest.mkdir(); subprocess.run(['git','-C',repo,'archive',ref],stdout=(root/'source.tar').open('wb'),check=True)
 with tarfile.open(root/'source.tar') as t: t.extractall(dest)
 return call(['git','-C',repo,'rev-parse',ref]).strip()
def run(args,cwd):
 with (root/'build.log').open('ab') as log: subprocess.run(args,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,check=True)
a=root/'ab3p';n=root/'ncbi';base=root/'baseline'
asrc=export(os.environ['AB3P_SOURCE'],a);nsrc=export(os.environ['NCBI_SOURCE'],n)
export(os.environ['AB3P_SOURCE'],base,'41130cddfcba1449ba612905d4a51274f8f565a8')
cxx=shutil.which('g++'); flags='-O2 -std=c++11 -static-libstdc++ -static-libgcc'
run(['make','-C',str(n/'lib')],root)
for src in [a,base]:
 (src/'path_Ab3P').write_text(str(src/'WordData')+'/\n')
 run(['make','NCBITEXTLIB='+str(n),'CXX='+cxx,'OS='+flags,'all'],src)
run([cxx,'-std=c++11','-I'+str(a/'lib'),'-I'+str(n/'include'),str(a/'run_support/native_probe.C'),'-L'+str(a/'lib'),'-lAb3P','-L'+str(n/'lib'),'-lText','-o',str(a/'native_probe')],a)
bundle=root/'bundle';(bundle/'bin').mkdir(parents=True)
shutil.copy2(a/'identify_abbr_jsonl',bundle/'bin/identify_abbr_jsonl');shutil.copytree(a/'WordData',bundle/'WordData')
(bundle/'NOTICE').write_text('Ab3P source README (upstream supplies no separate LICENSE):\n'+(a/'README.md').read_text()+'\nNCBITextLib:\n'+(n/'LICENSE').read_text())
hashes={str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(bundle.rglob('*')) if p.is_file()}
info={'bundle_schema':1,'driver_schema':1,'ab3p_sha':asrc,'ncbitextlib_sha':nsrc,'platform':'linux-x86_64','bits':64,'byteorder':'little','tested_glibc':call(['getconf','GNU_LIBC_VERSION']).strip(),'compiler':call([cxx,'--version']),'make':call(['make','--version']),'flags':flags,'members':hashes,'ldd':call(['ldd',str(bundle/'bin/identify_abbr_jsonl')]),'readelf':call(['readelf','-d',str(bundle/'bin/identify_abbr_jsonl')])}
(bundle/'build-info.json').write_text(json.dumps(info,indent=2)+'\n')
with tarfile.open(root/'ab3p-linux-x86_64.tar.gz','w:gz') as t:
 for p in sorted(bundle.iterdir()):t.add(p,arcname=p.name)
print(json.dumps(info,indent=2))
BUILD
