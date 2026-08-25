PulseSF is a lightweight, locally-hosted dashboard designed specifically for Solution Consultants (SCs). It connects directly to your Salesforce environment via the official Salesforce CLI, allowing you to bypass slow UI load times and manage your entire active pipeline, run advanced reports, and dynamically configure your workspace from a single, instant interface.

Core Features
Zero-Latency Editing: View, filter, and edit your Main Opportunity fields (including ARR Upsell), SC Records (POC__c), and MEDDPICC data in real-time.

Dynamic Column Engine: No more hardcoded tables. Use the "Edit Columns" menu to search and instantly add any field from the Opportunity or SC schema directly to your view, dragging and dropping to reorder them on the fly.

Advanced Reporting (Briefs): Instantly generate comprehensive "Closed Won" and "Opp Pipeline" dashboards. View interactive charts broken down by stage, team member, or historical month, and click any bar to drill down into the specific opportunities driving that data.

Pipeline Governance (Stage Sync Engine): PulseSF actively cross-references the Main Opportunity Sales Stage against your SC Stage.

🔴 Action Req: Flags deals where the Main Opportunity is Closed (Won/Lost), but the SC Record was left open.

⚠️ Out of Sync: Flags open deals where the Sales Stage has progressed, but the SC Stage is lagging behind (e.g., Sales is in "Negotiation" but SC is still in "Plan").

Predictive Analytics: Features a built-in dashboard mapping deal completion vs. stagnancy (untouched for >30 days) to help prioritize at-risk accounts.

One-Click Export: Export your currently filtered pipeline data directly to CSV, Excel (XLSX), or JSON with a single click.

Auto-Saving Drafts: Never lose your notes. Every keystroke is locally cached on your machine. If your internet drops or you accidentally close the tab, your draft is saved and highlighted in yellow for you to easily restore and sync later.

Universal Enterprise Error Handling: If Salesforce rejects a save (e.g., due to a validation rule or a locked record), PulseSF intercepts the exact API error and displays it in a clean modal, complete with a copy button and a link to your local server logs.

*** Installation & Setup (macOS)
PulseSF runs via a self-contained local web server and uses a Python Virtual Environment to comply with modern macOS security standards.

Prerequisites:
Python 3: Pre-installed on almost all Macs.

Salesforce CLI: The launch script will attempt to auto-install this for you via npm or brew if you don't already have it.

Step-by-Step Install:
Extract the Folder: Download PulseSF.zip and extract the folder to a permanent location on your Mac (e.g., your Documents folder).

Grant Execution Permissions (First Time Only):

Open the Terminal app.

Type exactly this: chmod +x  (Make sure you include the space after the 'x')

Drag and drop the PulseSF.command file from Finder into the Terminal window.

Press Enter.

Launch the Workspace:

Double-click the PulseSF.command file in Finder.

First Boot: A terminal window will open, create a secure Python environment, install necessary libraries, and pop open a web browser asking you to log into Salesforce via SSO.

Subsequent Boots: Takes less than 3 seconds to spin up.

**** How to Use PulseSF
Navigating the Workspace
Universal Search: Use the search bar to instantly filter your pipeline by Account Name, Opportunity Name, Opp Owner, SC, Opp ID, or SC Record ID.

Left Panel: Displays your active pipeline. Use the top dropdowns to filter by Stage, Fiscal Year, or Timeline (e.g., Closing This Month).

Right Panel: Click any row in the pipeline to load its data into the right-hand editor.

Hyperlinks: URLs and Record IDs (like Opportunity ID or Validation Plan links) are displayed in blue text. Click them once to instantly open the record in a new browser tab.

Syncing Changes to Salesforce
Edit the text boxes or dropdowns in the right panel.

Click 💾 Save Current Notes or 💾 Save Property Matrix Updates at the bottom of the panel.

Bulk Sync: Alternatively, check the boxes [☑] next to multiple rows in the pipeline and click the green 🚀 Sync Checked button at the top to push everything to Salesforce in one batch.

The "Force Refresh" Button
If your Salesforce Admin just added a new dropdown value, or you need to pull in a fresh schema configuration, click the 🔄 Force Refresh Schema and Data button at the top of the screen. This forcefully clears your local cache and downloads the absolute latest configurations from Salesforce.

*** Troubleshooting
Blank Dropdowns: Ensure you are actively connected to the internet. If an issue persists, click the "Force Refresh" button at the top.

System Error / Save Failed Modal: If you get a red error modal when saving, read the message. It is almost always a native Salesforce Validation Rule (e.g., "Cannot edit Closed Lost opportunities" or "Bad value for restricted picklist"). Adjust your fields accordingly and try saving again.

Checking Logs: If the app behaves unexpectedly, click the Settings ⚙️ button, or click the 📄 View Server Logs link inside any error modal. Logs are stored locally in the PulseSF/logs/ folder.

App Won't Open: Ensure your terminal hasn't lost its Salesforce connection. Open your Mac Terminal and type sf org login web --alias pd-workorg to manually refresh your session.

Built to make SC workflows fast, safe, and efficient.
