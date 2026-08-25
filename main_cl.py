from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.responses import PlainTextResponse
import asyncio
import json
import traceback
import os
import signal
import threading
import re
import subprocess
from datetime import datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Configuration Variables
SF_ORG = "pd-workorg"
SF_INSTANCE_URL = os.environ.get("SF_INSTANCE_URL", "https://pagerduty.my.salesforce.com")

user_cache = {}
schema_cache = {}

# Global Semaphore to prevent CPU choking and Salesforce API rate-limiting.
# Restricts the system to a maximum of 5 concurrent Salesforce CLI processes.
cli_semaphore = asyncio.Semaphore(5)

def log_activity(action: str, status: str, details: str = ""):
    now = datetime.now()
    month_folder = os.path.join("logs", now.strftime("%Y-%m"))
    os.makedirs(month_folder, exist_ok=True)
    daily_file = os.path.join(month_folder, f"{now.strftime('%Y-%m-%d')}.txt")
    with open(daily_file, "a") as f:
        f.write(f"[{now.strftime('%H:%M:%S')}] [{action}] [{status}] {details}\n")

def soql_escape(value: str) -> str:
    # Defense-in-depth for values interpolated into SOQL strings below.
    # Values here come from trusted CLI/API output, not raw user input, but
    # escaping keeps that true even if a future change starts using request data.
    return value.replace("\\", "\\\\").replace("'", "\\'")

def extract_cli_error(stdout: str, stderr: str) -> str:
    try:
        data = json.loads(stdout)
        if isinstance(data, list) and len(data) > 0:
            return data[0].get("message", str(data[0]))
        elif isinstance(data, dict):
            return data.get("message", stdout)
        return stdout
    except:
        clean_err = stderr.strip()
        clean_out = stdout.strip()
        if clean_err and clean_out: return f"{clean_err} | {clean_out}"
        return clean_err or clean_out or "Unknown Salesforce API Error. Check the terminal logs."

@app.get("/api/logs/latest", response_class=PlainTextResponse)
async def get_latest_logs():
    now = datetime.now()
    log_file = os.path.join("logs", now.strftime("%Y-%m"), f"{now.strftime('%Y-%m-%d')}.txt")
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            return f.read()
    return "No logs have been generated for today yet."

@app.get("/")
@app.get("/PulseSF")
async def serve_workspace(request: Request):
    # Derive the Lightning UI domain from the configured instance instead of hardcoding
    # an org-specific domain in the frontend, so "open in Salesforce" links stay correct
    # if SF_INSTANCE_URL is ever pointed at a different org (e.g. a sandbox).
    lightning_base = SF_INSTANCE_URL.replace(".my.salesforce.com", ".lightning.force.com")
    return templates.TemplateResponse(request=request, name="index_cl.html", context={"lightning_base": lightning_base})

async def run_sf_cmd(*args, timeout=30):
    sf_env = os.environ.copy()
    sf_env["SF_AUTOUPDATE_DISABLE"] = "true"
    sf_env["SF_DISABLE_AUTOUPDATE"] = "true"
    sf_env["SF_UPDATE_INSTRUCTIONS"] = "false"
    sf_env["SF_SKIP_NEW_VERSION_CHECK"] = "true"
    
    async with cli_semaphore:
        process = await asyncio.create_subprocess_exec(
            'sf', *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=sf_env
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            log_activity("SF_CMD", "TIMEOUT", f"Command timed out: {' '.join(args)}")
            return -1, "", "Salesforce CLI timed out."
            
    out_str = re.sub(r'\x1b\[[0-9;]*m', '', stdout.decode().strip())
    err_str = re.sub(r'\x1b\[[0-9;]*m', '', stderr.decode().strip())
    
    def strip_warnings(text):
        lines = text.split('\n')
        clean_lines = []
        for l in lines:
            if "Warning: @salesforce/cli update available" in l: continue
            if "Warning: This command is currently in beta" in l: continue
            if "Don't use beta commands in your scripts" in l: continue
            if l.strip().startswith("›"): continue
            clean_lines.append(l)
        return '\n'.join(clean_lines).strip()
        
    out_str = strip_warnings(out_str)
    err_str = strip_warnings(err_str)
    
    if out_str and not (out_str.startswith('{') or out_str.startswith('[')):
        match = re.search(r'[\{\[]', out_str)
        if match:
            out_str = out_str[match.start():]
        
    return process.returncode, out_str, err_str

@app.get("/api/schema")
async def get_schema(refresh: bool = False):
    global schema_cache
    if schema_cache and not refresh: 
        return {"status": "success", "data": schema_cache}
        
    code, stdout, stderr = await run_sf_cmd('sobject', 'describe', '--sobject', 'POC__c', '--target-org', SF_ORG, '--json')
    poc_picklists = {}
    poc_fields = []
    
    if code == 0:
        fields = json.loads(stdout).get('result', {}).get('fields', [])
        poc_fields = [f['name'] for f in fields]
        for f in fields:
            if f.get('type', '').lower() in ['picklist', 'multipicklist', 'combobox']:
                poc_picklists[f['name']] = [p['value'] for p in f.get('picklistValues', []) if p.get('active', True)]
                
    code2, stdout2, stderr2 = await run_sf_cmd('sobject', 'describe', '--sobject', 'Opportunity', '--target-org', SF_ORG, '--json')
    meddpicc_fields = []
    opp_fields = []
    if code2 == 0:
        o_fields = json.loads(stdout2).get('result', {}).get('fields', [])
        opp_fields = [f['name'] for f in o_fields]
        kws = ['metric', 'economic', 'decision', 'pain', 'champion', 'competi', 'meddpicc', 'paper process']
        for f in o_fields:
            if f['name'] not in ['Name', 'StageName', 'NextStep', 'Description', 'Id']:
                if any(kw in f['name'].lower() for kw in kws) or any(kw in f.get('label','').lower() for kw in kws):
                    meddpicc_fields.append({"name": f['name'], "label": f['label']})
                    
    schema_cache = {
        'poc_picklists': poc_picklists, 
        'meddpicc': meddpicc_fields,
        'poc_fields': poc_fields,
        'opp_fields': opp_fields
    }
    log_activity("SCHEMA_FETCH", "SUCCESS", "Dynamic picklists and schema loaded")
    return {"status": "success", "data": schema_cache}

@app.get("/api/auth/status")
async def check_auth_status():
    code, stdout, _ = await run_sf_cmd('org', 'display', '--target-org', SF_ORG, '--json')
    if code == 0: return {"status": "success"}
    return {"status": "auth_required"}

@app.post("/api/auth/login")
async def trigger_sf_login():
    try:
        await asyncio.create_subprocess_shell(f"sf org login web --alias {SF_ORG} --instance-url {SF_INSTANCE_URL}")
        log_activity("LOGIN", "PENDING", f"Triggered web login window for {SF_INSTANCE_URL}")
        return {"status": "success", "message": "Login window opened."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def execute_self_destruct(delay=0.5):
    import time; time.sleep(delay)
    pid = os.getpid()
    subprocess.Popen(
        f"osascript -e 'tell application \"Terminal\" to close front window saving no' && kill -9 {pid}", 
        shell=True, 
        start_new_session=True
    )

@app.post("/api/shutdown")
async def shutdown_server():
    log_activity("SYSTEM", "SHUTDOWN", "Browser tab closed, killing server")
    threading.Thread(target=execute_self_destruct, args=(0.5,)).start()
    return {"status": "shutting down"}

@app.post("/api/auth/logout")
async def trigger_sf_logout():
    try:
        await run_sf_cmd('org', 'logout', '--target-org', SF_ORG, '--no-prompt')
        log_activity("LOGIN", "LOGOUT", "User logged out securely")
        threading.Thread(target=execute_self_destruct, args=(1.5,)).start()
        return {"status": "success"}
    except Exception as e: return {"status": "error"}

@app.get("/api/opportunities")
async def get_opportunities(refresh: bool = False):
    global user_cache
    try:
        if not schema_cache or refresh: await get_schema(refresh=True)
        
        valid_poc = schema_cache.get('poc_fields', [])
        valid_opp = schema_cache.get('opp_fields', [])

        if SF_ORG not in user_cache:
            code, stdout, stderr = await run_sf_cmd('org', 'display', '--target-org', SF_ORG, '--json')
            if code != 0: return {"status": "auth_required", "message": "No active Salesforce session found."}
            username = json.loads(stdout)['result']['username']
            code, id_stdout, _ = await run_sf_cmd('data', 'query', '-q', f"SELECT Id FROM User WHERE Username='{soql_escape(username)}'", '--target-org', SF_ORG, '--json')
            user_cache[SF_ORG] = json.loads(id_stdout)['result']['records'][0]['Id']
            
        user_id = user_cache[SF_ORG]
        
        opp_wishlist = ['Id', 'Name', 'AccountId', 'Type', 'Amount', 'Probability', 'CloseDate', 'StageName', 'OwnerId', 'NextStep', 'CreatedDate', 'LastModifiedDate', 'Sales_Motion__c', 'Current_Status__c', 'SC_Notes__c']
        safe_opp = list(set([f for f in opp_wishlist if f in valid_opp]))
        if 'AccountId' in valid_opp: safe_opp.append('Account.Name')
        if 'OwnerId' in valid_opp: safe_opp.append('Owner.Name')
        for m in [f["name"] for f in schema_cache.get('meddpicc', [])]:
            if m in valid_opp and m not in safe_opp: safe_opp.append(m)
        opp_select = ", ".join(safe_opp)

        safe_poc = [f for f in valid_poc if f.endswith('__c') or f in ['Id', 'Name', 'CreatedDate', 'LastModifiedDate']]
        if 'Sales_Lead__c' in valid_poc: safe_poc.append('Sales_Lead__r.Name')
        if 'Solution_Consultant__c' in valid_poc: safe_poc.append('Solution_Consultant__r.Name')
        poc_select = ", ".join(list(set(safe_poc))) if safe_poc else "Id, Name"

        safe_user_id = soql_escape(user_id)
        soql_query = (
            f"SELECT {opp_select}, "
            f"(SELECT {poc_select} FROM POCs__r ORDER BY CreatedDate DESC LIMIT 1), "
            f"(SELECT Id, UserId, User.Name, TeamMemberRole, OpportunityAccessLevel FROM OpportunityTeamMembers WHERE UserId = '{safe_user_id}') "
            f"FROM Opportunity WHERE Id IN (SELECT OpportunityId FROM OpportunityTeamMember WHERE UserId = '{safe_user_id}') ORDER BY LastModifiedDate DESC"
        )
        
        code, query_stdout, query_stderr = await run_sf_cmd('data', 'query', '-q', soql_query, '--target-org', SF_ORG, '--json')
        if code == 0:
            records = json.loads(query_stdout).get('result', {}).get('records', [])
            log_activity("DATA_FETCH", "SUCCESS", f"Pulled {len(records)} opportunities")
            return {"status": "success", "data": records}
        else:
            err = extract_cli_error(query_stdout, query_stderr)
            log_activity("DATA_FETCH", "ERROR", err)
            return {"status": "error", "message": err}
    except Exception as e:
        log_activity("DATA_FETCH", "CRASH", str(e))
        return {"status": "error", "message": str(e)}

@app.get("/api/meddpicc/{opp_id}")
async def get_meddpicc(opp_id: str):
    try:
        code, stdout, stderr = await run_sf_cmd('data', 'get', 'record', '--sobject', 'Opportunity', '--record-id', opp_id, '--target-org', SF_ORG, '--json')
        if code == 0:
            data = json.loads(stdout).get('result', {})
            keywords = ['metric', 'economic', 'decision', 'pain', 'champion', 'competi', 'meddpicc', 'paper process']
            meddpicc_data = []
            for k, v in data.items():
                if v and isinstance(v, str) and any(kw in k.lower() for kw in keywords):
                    if not k.endswith('Id') and k not in ['Name', 'StageName', 'NextStep', 'Description']:
                        clean_label = k.replace('__c', '').replace('_', ' ')
                        meddpicc_data.append({"label": clean_label, "value": v})
            meddpicc_data.sort(key=lambda x: x["label"])
            return {"status": "success", "data": meddpicc_data}
        else:
            err = extract_cli_error(stdout, stderr)
            return {"status": "error", "message": err}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class SaveRequest(BaseModel):
    opp_id: str
    poc_id: str = None
    opp_payload: dict = {}
    poc_payload: dict = {}

@app.post("/api/save")
async def save_to_salesforce(req: SaveRequest):
    try:
        valid_opp = schema_cache.get('opp_fields', [])
        valid_poc = schema_cache.get('poc_fields', [])

        if req.opp_payload:
            clean_opp = {k: v for k, v in req.opp_payload.items() if k in valid_opp}
            if not clean_opp:
                # valid_opp comes from schema_cache; if it's empty/stale, every key gets
                # filtered out here and the save would silently no-op while still
                # reporting "success" below. Fail loudly instead of losing the edit.
                err = "No valid Opportunity fields to save - schema cache looks stale. Click Force Refresh (🔄) and try saving again."
                log_activity("SAVE_OPP", "ERROR", f"Opp {req.opp_id} | {err}")
                return {"status": "error", "message": err}
            opp_endpoint = f"/services/data/v62.0/sobjects/Opportunity/{req.opp_id}"
            code, stdout, stderr = await run_sf_cmd('api', 'request', 'rest', opp_endpoint, '--method', 'PATCH', '--body', json.dumps(clean_opp), '--target-org', SF_ORG)
            if code != 0:
                err = extract_cli_error(stdout, stderr)
                log_activity("SAVE_OPP", "ERROR", f"Opp {req.opp_id} | {err}")
                return {"status": "error", "message": f"Opp Save Error: {err}"}

        if req.poc_payload and req.poc_id:
            clean_poc = {k: v for k, v in req.poc_payload.items() if k in valid_poc}
            if not clean_poc:
                err = "No valid SC/POC fields to save - schema cache looks stale. Click Force Refresh (🔄) and try saving again."
                log_activity("SAVE_POC", "ERROR", f"POC {req.poc_id} | {err}")
                return {"status": "error", "message": err}
            poc_endpoint = f"/services/data/v62.0/sobjects/POC__c/{req.poc_id}"
            code, stdout, stderr = await run_sf_cmd('api', 'request', 'rest', poc_endpoint, '--method', 'PATCH', '--body', json.dumps(clean_poc), '--target-org', SF_ORG)
            if code != 0:
                err = extract_cli_error(stdout, stderr)
                log_activity("SAVE_POC", "ERROR", f"POC {req.poc_id} | {err}")
                return {"status": "error", "message": f"POC Save Error: {err}"}
        
        log_activity("SAVE_SUCCESS", "SUCCESS", f"Opp {req.opp_id} / POC {req.poc_id} updated")
        return {"status": "success"}
    except Exception as e:
        log_activity("SAVE_CRASH", "ERROR", str(e))
        return {"status": "error", "message": str(e)}