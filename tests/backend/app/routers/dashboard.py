"""Web Dashboard – summary API endpoints for the dashboard UI."""
from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>stud dashboard</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;min-height:100vh}
#app{max-width:1200px;margin:0 auto;padding:24px}
header{display:flex;align-items:center;gap:12px;margin-bottom:32px;padding-bottom:16px;border-bottom:1px solid #21262d}
header h1{font-size:20px;font-weight:600}
.pill{background:#238636;color:#fff;padding:2px 8px;border-radius:12px;font-size:11px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:32px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px}
.card h3{font-size:13px;color:#8b949e;margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px}
.card .num{font-size:28px;font-weight:700;color:#58a6ff}
.card .sub{font-size:12px;color:#8b949e;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:13px}
thead th{padding:8px 12px;text-align:left;background:#161b22;border-bottom:1px solid #30363d;color:#8b949e;font-weight:500}
tbody tr{border-bottom:1px solid #21262d}
tbody tr:hover{background:#161b22}
td{padding:8px 12px}
.badge{padding:2px 8px;border-radius:12px;font-size:11px;font-weight:500}
.badge.open{background:#388bfd26;color:#58a6ff}
.badge.merged{background:#8957e526;color:#a371f7}
.badge.closed{background:#3d444d;color:#8b949e}
.badge.done{background:#238636;color:#fff}
.badge.failed{background:#da3633;color:#fff}
.badge.pending,.badge.running{background:#9e6a03;color:#e3b341}
section{margin-bottom:32px}
section h2{font-size:16px;margin-bottom:12px;color:#e6edf3}
.tabs{display:flex;gap:4px;margin-bottom:24px}
.tab{padding:6px 16px;border-radius:6px;border:1px solid #30363d;background:transparent;color:#8b949e;cursor:pointer;font-size:13px}
.tab.active{background:#238636;color:#fff;border-color:#238636}
#login-form{display:flex;flex-direction:column;gap:12px;max-width:320px;margin:80px auto}
#login-form h2{font-size:18px}
input{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:8px 12px;color:#e6edf3;font-size:13px;width:100%}
input:focus{outline:none;border-color:#58a6ff}
button{background:#238636;color:#fff;border:none;border-radius:6px;padding:8px 16px;cursor:pointer;font-size:13px}
button:hover{background:#2ea043}
.err{color:#f85149;font-size:12px}
a{color:#58a6ff;text-decoration:none}
a:hover{text-decoration:underline}
</style>
</head>
<body>
<div id="root"></div>
<script>
const API = '';
let token = localStorage.getItem('stud_token');
let username = localStorage.getItem('stud_username');

async function api(path, opts={}) {
  const headers = {'Content-Type':'application/json'};
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const r = await fetch(API + path, {...opts, headers});
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function login(u, p) {
  const data = await api('/auth/login', {method:'POST', body: JSON.stringify({username:u,password:p})});
  token = data.token; username = data.username;
  localStorage.setItem('stud_token', token);
  localStorage.setItem('stud_username', username);
  render();
}

function logout() {
  token = null; username = null;
  localStorage.removeItem('stud_token');
  localStorage.removeItem('stud_username');
  render();
}

function el(tag, attrs={}, ...children) {
  const e = document.createElement(tag);
  for (const [k,v] of Object.entries(attrs)) {
    if (k==='class') e.className=v;
    else if (k.startsWith('on')) e[k]=v;
    else e.setAttribute(k,v);
  }
  for (const c of children) {
    if (c==null) continue;
    e.appendChild(typeof c==='string'?document.createTextNode(c):c);
  }
  return e;
}

function badge(status) {
  return el('span',{class:`badge ${status}`}, status);
}

// ── Login Screen ────────────────────────────────────────────────────────────
function renderLogin() {
  const errEl = el('p',{class:'err'});
  const uIn = el('input',{type:'text',placeholder:'Username'});
  const pIn = el('input',{type:'password',placeholder:'Password'});
  const btn = el('button',{}, 'Sign in');
  btn.onclick = async () => {
    try { await login(uIn.value, pIn.value); }
    catch(e) { errEl.textContent = 'Login failed: ' + e.message; }
  };
  const form = el('div',{id:'login-form'},
    el('h2',{},'Sign in to stud'),
    uIn, pIn, btn, errEl
  );
  document.getElementById('root').replaceChildren(form);
}

// ── Main Dashboard ───────────────────────────────────────────────────────────
let _tab = 'repos';
async function renderDashboard() {
  const root = document.getElementById('root');
  root.innerHTML = '<div id="app"><p style="color:#8b949e">Loading…</p></div>';

  const [repos, runners, stats] = await Promise.all([
    api('/repos'),
    api('/runners').catch(()=>[]),
    api('/dashboard/stats').catch(()=>({repos:0,prs:0,scans:0,deployments:0})),
  ]);

  const header = el('header',{},
    el('h1',{},'🛠 stud'),
    el('span',{class:'pill'}, username),
    el('button',{onclick:logout, style:'margin-left:auto;background:#21262d'}, 'Sign out')
  );

  const grid = el('div',{class:'grid'},
    statCard('Repositories', stats.repos||repos.length, 'total'),
    statCard('Pull Requests', stats.prs||0, 'open'),
    statCard('Scans', stats.scans||0, 'completed'),
    statCard('Deployments', stats.deployments||0, 'total'),
    statCard('Runners', runners.length, runners.filter(r=>r.status==='online').length+' online'),
  );

  function statCard(title, num, sub) {
    return el('div',{class:'card'},
      el('h3',{},title),
      el('div',{class:'num'},String(num)),
      el('div',{class:'sub'},String(sub))
    );
  }

  const tabs = el('div',{class:'tabs'},
    ...['repos','prs','runners','scans','deployments'].map(t =>
      el('button',{class:'tab'+(_tab===t?' active':''), onclick:()=>{_tab=t;renderDashboard();}}, t)
    )
  );

  let section;
  if (_tab==='repos') section = reposSection(repos);
  else if (_tab==='prs') section = await prsSection(repos);
  else if (_tab==='runners') section = runnersSection(runners);
  else if (_tab==='scans') section = await scansSection(repos);
  else if (_tab==='deployments') section = await deploysSection(repos);

  const app = el('div',{id:'app'}, header, grid, tabs, section);
  root.replaceChildren(app);
}

function reposSection(repos) {
  const rows = repos.map(r =>
    el('tr',{},
      el('td',{},el('a',{href:`#`},`${r.owner}/${r.name}`)),
      el('td',{},r.private?'🔒 private':'public'),
      el('td',{},r.default_branch),
    )
  );
  return el('section',{},
    el('h2',{},'Repositories'),
    el('table',{},
      el('thead',{},el('tr',{},el('th',{},'Name'),el('th',{},'Visibility'),el('th',{},'Default Branch'))),
      el('tbody',{},...rows)
    )
  );
}

async function prsSection(repos) {
  const allPRs = (await Promise.all(
    repos.map(r => api(`/repos/${r.owner}/${r.name}/pulls`).catch(()=>[]))
  )).flat();
  const rows = allPRs.map(p =>
    el('tr',{},
      el('td',{},`#${p.number}`),
      el('td',{},p.title),
      el('td',{},p.author),
      el('td',{},badge(p.status)),
      el('td',{},p.base_branch,'←',p.head_branch),
    )
  );
  return el('section',{},
    el('h2',{},'Pull Requests'),
    rows.length ? el('table',{},
      el('thead',{},el('tr',{},...['#','Title','Author','Status','Branches'].map(h=>el('th',{},h)))),
      el('tbody',{},...rows)
    ) : el('p',{style:'color:#8b949e'},'No pull requests found.')
  );
}

function runnersSection(runners) {
  const rows = runners.map(r =>
    el('tr',{},
      el('td',{},r.name),
      el('td',{},badge(r.status)),
      el('td',{},r.os+'/'+r.arch),
      el('td',{},r.labels),
      el('td',{},r.last_seen_at?new Date(r.last_seen_at*1000).toLocaleString():'—'),
    )
  );
  return el('section',{},
    el('h2',{},'Self-Hosted Runners'),
    rows.length ? el('table',{},
      el('thead',{},el('tr',{},...['Name','Status','OS/Arch','Labels','Last Seen'].map(h=>el('th',{},h)))),
      el('tbody',{},...rows)
    ) : el('p',{style:'color:#8b949e'},'No runners registered.')
  );
}

async function scansSection(repos) {
  const allScans = (await Promise.all(
    repos.map(r => api(`/repos/${r.owner}/${r.name}/scans`).catch(()=>[]))
  )).flat().slice(0,50);
  const rows = allScans.map(s =>
    el('tr',{},
      el('td',{},s.repo),
      el('td',{},badge(s.status)),
      el('td',{},s.findings.length+' findings'),
      el('td',{},new Date(s.created_at*1000).toLocaleString()),
    )
  );
  return el('section',{},
    el('h2',{},'Dependency Scans'),
    rows.length ? el('table',{},
      el('thead',{},el('tr',{},...['Repo','Status','Findings','Triggered'].map(h=>el('th',{},h)))),
      el('tbody',{},...rows)
    ) : el('p',{style:'color:#8b949e'},'No scans found.')
  );
}

async function deploysSection(repos) {
  const allDeploys = (await Promise.all(
    repos.map(r => api(`/repos/${r.owner}/${r.name}/deployments`).catch(()=>[]))
  )).flat().slice(0,50);
  const rows = allDeploys.map(d =>
    el('tr',{},
      el('td',{},d.namespace),
      el('td',{},`${d.image}:${d.tag}`),
      el('td',{},String(d.replicas)),
      el('td',{},badge(d.status)),
      el('td',{},new Date(d.created_at*1000).toLocaleString()),
    )
  );
  return el('section',{},
    el('h2',{},'Kubernetes Deployments'),
    rows.length ? el('table',{},
      el('thead',{},el('tr',{},...['Namespace','Image','Replicas','Status','Deployed'].map(h=>el('th',{},h)))),
      el('tbody',{},...rows)
    ) : el('p',{style:'color:#8b949e'},'No deployments found.')
  );
}

// ── Bootstrap ────────────────────────────────────────────────────────────────
function render() {
  if (!token) { renderLogin(); return; }
  renderDashboard().catch(e => { console.error(e); renderLogin(); });
}
render();
</script>
</body>
</html>"""


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def dashboard_ui():
    return HTMLResponse(_DASHBOARD_HTML)


@router.get("/stats")
def dashboard_stats(
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_ids = [
        r.id for r in
        db.query(models.Repository).filter(models.Repository.owner_id == user.id).all()
    ]

    pr_count = 0
    scan_count = 0
    deploy_count = 0
    if repo_ids:
        pr_count = (
            db.query(func.count(models.PullRequest.id))
            .filter(models.PullRequest.repo_id.in_(repo_ids))
            .scalar() or 0
        )
        scan_count = (
            db.query(func.count(models.DependencyScan.id))
            .filter(models.DependencyScan.repo_id.in_(repo_ids))
            .scalar() or 0
        )
        deploy_count = (
            db.query(func.count(models.K8sDeployment.id))
            .filter(models.K8sDeployment.repo_id.in_(repo_ids))
            .scalar() or 0
        )

    return {
        "repos": len(repo_ids),
        "prs": pr_count,
        "scans": scan_count,
        "deployments": deploy_count,
    }
