# Apple Health → Nanobot iOS Shortcut Setup

## Step 1: Start nanobot API server

On your computer, run:
```
nanobot serve --host 0.0.0.0 --port 8900
```

Note the IP address of your computer on your local network:
- **Mac**: System Settings → Network → look for your IP (e.g., `192.168.1.100`)
- **Windows**: Open PowerShell, run `ipconfig`, look for "IPv4 Address" under your active adapter

Your webhook URL will be: `http://YOUR_COMPUTER_IP:8900/webhook/apple-health`

## Step 2: Create the iOS Shortcut

1. Open the **Shortcuts** app on your iPhone
2. Tap **+** (top right) to create a new shortcut
3. Tap the name at the top → rename to **"Sync Health to Nanobot"**
4. Add the following actions in order:

---

### Action 1: Get Health Samples — Steps
- Tap **Add Action** → search **"Find Health Samples"**
- Set **Health Type** to `Steps`
- Set **Start Date** to `Today at 12:00 AM`
- Set **End Date** to `Today at 11:59 PM`
- Tap the arrow next to the action → turn on **Show in Share Sheet** (optional)

### Action 2: Get Health Samples — Active Energy
- Tap **Add Action** → search **"Find Health Samples"**
- Set **Health Type** to `Active Energy`
- Set **Start Date** to `Today at 12:00 AM`
- Set **End Date** to `Today at 11:59 PM`

### Action 3: Get Health Samples — Resting Heart Rate
- Tap **Add Action** → search **"Find Health Samples"**
- Set **Health Type** to `Resting Heart Rate`
- Set **Start Date** to `Today at 12:00 AM`
- Set **End Date** to `Today at 11:59 PM`

### Action 4: Get Health Samples — Body Mass
- Tap **Add Action** → search **"Find Health Samples"**
- Set **Health Type** to `Body Mass`
- Set **Start Date** to `Today at 12:00 AM`
- Set **End Date** to `Today at 11:59 PM`

### Action 5: Get Health Samples — Body Fat Percentage
- Tap **Add Action** → search **"Find Health Samples"**
- Set **Health Type** to `Body Fat Percentage`
- Set **Start Date** to `Today at 12:00 AM`
- Set **End Date** to `Today at 11:59 PM`

### Action 6: Get Health Samples — Sleep Analysis
- Tap **Add Action** → search **"Find Health Samples"**
- Set **Health Type** to `Sleep Analysis`
- Set **Start Date** to `Yesterday at 12:00 AM`
- Set **End Date** to `Today at 11:59 PM`

### Action 7: Get Health Samples — Heart Rate Variability
- Tap **Add Action** → search **"Find Health Samples"**
- Set **Health Type** to `Heart Rate Variability SDNN`
- Set **Start Date** to `Today at 12:00 AM`
- Set **End Date** to `Today at 11:59 PM`

### Action 8: Get Health Samples — Blood Glucose (optional)
- Tap **Add Action** → search **"Find Health Samples"**
- Set **Health Type** to `Blood Glucose`
- Set **Start Date** to `Today at 12:00 AM`
- Set **End Date** to `Today at 11:59 PM`

### Action 9: Get Health Samples — Blood Pressure (optional)
- Tap **Add Action** → search **"Find Health Samples"**
- Set **Health Type** to `Blood Pressure Systolic`
- Set **Start Date** to `Today at 12:00 AM`
- Set **End Date** to `Today at 11:59 PM`

### Action 10: Get Health Samples — Dietary Water (optional)
- Tap **Add Action** → search **"Find Health Samples"**
- Set **Health Type** to `Dietary Water`
- Set **Start Date** to `Today at 12:00 AM`
- Set **End Date** to `Today at 11:59 PM`

### Action 11: Build JSON
- Tap **Add Action** → search **"Dictionary"**
- Add key-value pairs for each health type:
  - Key: `type`, Value: `health_data`
  - Key: `date`, Value: `Current Date` → format as `yyyy-MM-dd`
  - Key: `steps`, Value: tap **Steps** from the first Health action → use **Get Details** → `Value`
  - Key: `active_energy`, Value: tap **Active Energy** → Get Details → `Value`
  - Key: `resting_hr`, Value: tap **Resting Heart Rate** → Get Details → `Value`
  - Key: `body_mass`, Value: tap **Body Mass** → Get Details → `Value`
  - Key: `body_fat`, Value: tap **Body Fat %** → Get Details → `Value`
  - Key: `hrv`, Value: tap **HRV** → Get Details → `Value`

### Action 12: Send to Nanobot
- Tap **Add Action** → search **"Get Contents of URL"**
- Set URL to: `http://YOUR_COMPUTER_IP:8900/webhook/apple-health`
- Set Method to **POST**
- Expand **Request Body** → set to the Dictionary from Action 11
- Set **Headers**: Add `Content-Type: application/json`

### Action 13: Show Result (optional)
- Tap **Add Action** → search **"Show Result"**
- Set it to show the response from the URL action

---

## Step 3: Set up Automation (run automatically)

1. Open Shortcuts → tap **Automation** tab (bottom)
2. Tap **+** → **Create Personal Automation**
3. Choose **Time of Day**
4. Set to your preferred time (e.g., 8:00 AM daily)
5. Tap **Next** → **Add Action** → search **"Run Shortcut"**
6. Select your **"Sync Health to Nanobot"** shortcut
7. Turn **OFF** "Ask Before Running" and "Notify When Run"
8. Tap **Done**

---

## Alternative: Simpler Shortcut (text-based)

If the above is too complex, here's a simpler version:

1. Add Action → **Find Health Samples** → Steps → Today
2. Add Action → **Get Details** → Value
3. Add Action → **Find Health Samples** → Body Mass → Today
4. Add Action → **Get Details** → Value
5. Add Action → **Text** and compose:
   ```
   Apple Health data for today:
   Steps: [Steps value]
   Weight: [Body Mass value] kg
   ```
6. Add Action → **Get Contents of URL**
   - URL: `http://YOUR_COMPUTER_IP:8900/webhook/apple-health`
   - Method: POST
   - Request Body: the Text from step 5
   - Header: `Content-Type: application/json`

---

## Troubleshooting

**"Connection refused"** — Make sure:
- `nanobot serve` is running with `--host 0.0.0.0`
- Your computer and iPhone are on the same WiFi network
- Your computer's firewall allows incoming connections on port 8900

**Health permission prompt** — When you first run the shortcut, iOS will ask permission to read each Health type. Tap **Allow**.

**Shortcut fails silently** — Add a **Show Alert** action at the end to see the response from the webhook.
