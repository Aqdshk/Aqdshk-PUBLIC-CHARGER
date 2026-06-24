$base    = "https://charger.czeros.tech/monitoring/api/v1/provisioning/alert-rules"
$auth    = "Basic " + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("admin:PlagSiniGraf2026"))
$folder  = "c4da57fe-4f3e-4845-bdad-3318899ee03a"
$loki    = "loki"
$expr    = "-100"
$headers = @{ Authorization = $auth; "Content-Type" = "application/json; charset=utf-8" }

function Post-Rule($json) {
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    $req   = [Net.HttpWebRequest]::Create($base)
    $req.Method      = "POST"
    $req.ContentType = "application/json; charset=utf-8"
    $req.Headers["Authorization"] = $auth
    $req.ContentLength = $bytes.Length
    $s = $req.GetRequestStream(); $s.Write($bytes,0,$bytes.Length); $s.Close()
    try {
        $r = $req.GetResponse()
        $reader = New-Object IO.StreamReader($r.GetResponseStream())
        Write-Host "OK:" $reader.ReadToEnd()
    } catch [Net.WebException] {
        $reader = New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "ERR:" $reader.ReadToEnd()
    }
}

# ── 1. API / App Down ─────────────────────────────────────────────────────
Post-Rule (@"
{
  "orgID":1,"folderUID":"$folder","ruleGroup":"PlagSini System",
  "title":"API / App Down","condition":"C","for":"5m",
  "noDataState":"Alerting","execErrState":"Error",
  "annotations":{
    "summary":"🌐 Aplikasi Tidak Dapat Diakses!",
    "description":"Tiada aktiviti dikesan dari server dalam 5 minit. Kemungkinan aplikasi atau API mengalami gangguan serius."
  },
  "labels":{"severity":"critical","team":"plagsini"},
  "data":[
    {"refId":"A","queryType":"range","relativeTimeRange":{"from":300,"to":0},"datasourceUid":"$loki",
     "model":{"expr":"count_over_time({job=\"charging-platform\"} [5m])","queryType":"range","refId":"A","intervalMs":1000,"maxDataPoints":43200}},
    {"refId":"B","queryType":"","relativeTimeRange":{"from":300,"to":0},"datasourceUid":"$expr",
     "model":{"type":"reduce","expression":"A","reducer":"last","refId":"B","datasource":{"type":"__expr__","uid":"$expr"},"intervalMs":1000,"maxDataPoints":43200}},
    {"refId":"C","queryType":"","relativeTimeRange":{"from":300,"to":0},"datasourceUid":"$expr",
     "model":{"type":"threshold","expression":"B","conditions":[{"evaluator":{"params":[1],"type":"lt"},"operator":{"type":"and"},"query":{"params":["B"]},"reducer":{"type":"last"},"type":"query"}],"refId":"C","datasource":{"type":"__expr__","uid":"$expr"},"intervalMs":1000,"maxDataPoints":43200}}
  ]
}
"@)

# ── 2. Database Error ─────────────────────────────────────────────────────
Post-Rule (@"
{
  "orgID":1,"folderUID":"$folder","ruleGroup":"PlagSini System",
  "title":"Database Connection Error","condition":"C","for":"2m",
  "noDataState":"OK","execErrState":"Error",
  "annotations":{
    "summary":"💾 Ralat Database Dikesan!",
    "description":"Ralat sambungan database dikesan. Data transaksi mungkin tidak disimpan. Sila semak segera."
  },
  "labels":{"severity":"critical","team":"plagsini"},
  "data":[
    {"refId":"A","queryType":"range","relativeTimeRange":{"from":300,"to":0},"datasourceUid":"$loki",
     "model":{"expr":"count_over_time({job=\"charging-platform\"} |~ \"(?i)(OperationalError|database.*error|mysql.*fail|connection.*refused|sqlalchemy)\" [5m])","queryType":"range","refId":"A","intervalMs":1000,"maxDataPoints":43200}},
    {"refId":"B","queryType":"","relativeTimeRange":{"from":300,"to":0},"datasourceUid":"$expr",
     "model":{"type":"reduce","expression":"A","reducer":"last","refId":"B","datasource":{"type":"__expr__","uid":"$expr"},"intervalMs":1000,"maxDataPoints":43200}},
    {"refId":"C","queryType":"","relativeTimeRange":{"from":300,"to":0},"datasourceUid":"$expr",
     "model":{"type":"threshold","expression":"B","conditions":[{"evaluator":{"params":[0],"type":"gt"},"operator":{"type":"and"},"query":{"params":["B"]},"reducer":{"type":"last"},"type":"query"}],"refId":"C","datasource":{"type":"__expr__","uid":"$expr"},"intervalMs":1000,"maxDataPoints":43200}}
  ]
}
"@)

# ── 3. Payment Failed Spike ───────────────────────────────────────────────
Post-Rule (@"
{
  "orgID":1,"folderUID":"$folder","ruleGroup":"PlagSini Business",
  "title":"Payment Failed Spike","condition":"C","for":"5m",
  "noDataState":"OK","execErrState":"Error",
  "annotations":{
    "summary":"💳 Masalah Pembayaran Dikesan!",
    "description":"Lebih 3 kegagalan bayaran dalam 10 minit. Kemungkinan ada masalah dengan sistem pembayaran atau gateway."
  },
  "labels":{"severity":"warning","team":"plagsini"},
  "data":[
    {"refId":"A","queryType":"range","relativeTimeRange":{"from":600,"to":0},"datasourceUid":"$loki",
     "model":{"expr":"count_over_time({job=\"charging-platform\"} |~ \"(?i)(payment.*fail|topup.*fail|transaction.*fail|payment.*error|charge.*fail)\" [10m])","queryType":"range","refId":"A","intervalMs":1000,"maxDataPoints":43200}},
    {"refId":"B","queryType":"","relativeTimeRange":{"from":600,"to":0},"datasourceUid":"$expr",
     "model":{"type":"reduce","expression":"A","reducer":"last","refId":"B","datasource":{"type":"__expr__","uid":"$expr"},"intervalMs":1000,"maxDataPoints":43200}},
    {"refId":"C","queryType":"","relativeTimeRange":{"from":600,"to":0},"datasourceUid":"$expr",
     "model":{"type":"threshold","expression":"B","conditions":[{"evaluator":{"params":[3],"type":"gt"},"operator":{"type":"and"},"query":{"params":["B"]},"reducer":{"type":"last"},"type":"query"}],"refId":"C","datasource":{"type":"__expr__","uid":"$expr"},"intervalMs":1000,"maxDataPoints":43200}}
  ]
}
"@)

# ── 4. Charging Session Stuck >3h ────────────────────────────────────────
Post-Rule (@"
{
  "orgID":1,"folderUID":"$folder","ruleGroup":"PlagSini Business",
  "title":"Charging Session Stuck","condition":"C","for":"3h",
  "noDataState":"OK","execErrState":"Error",
  "annotations":{
    "summary":"🔋 Sesi Cas Terlalu Lama!",
    "description":"Ada sesi pengecasan yang masih berjalan lebih 3 jam. Kemungkinan sesi tersekat atau pengguna terlupa cabut plug."
  },
  "labels":{"severity":"warning","team":"plagsini"},
  "data":[
    {"refId":"A","queryType":"range","relativeTimeRange":{"from":14400,"to":0},"datasourceUid":"$loki",
     "model":{"expr":"count_over_time({job=\"charging-platform\"} |~ \"(?i)(StartTransaction)\" [4h])","queryType":"range","refId":"A","intervalMs":1000,"maxDataPoints":43200}},
    {"refId":"B","queryType":"range","relativeTimeRange":{"from":14400,"to":0},"datasourceUid":"$loki",
     "model":{"expr":"count_over_time({job=\"charging-platform\"} |~ \"(?i)(StopTransaction)\" [4h])","queryType":"range","refId":"B","intervalMs":1000,"maxDataPoints":43200}},
    {"refId":"D","queryType":"","relativeTimeRange":{"from":14400,"to":0},"datasourceUid":"$expr",
     "model":{"type":"math","expression":"$A - $B","refId":"D","datasource":{"type":"__expr__","uid":"$expr"},"intervalMs":1000,"maxDataPoints":43200}},
    {"refId":"C","queryType":"","relativeTimeRange":{"from":14400,"to":0},"datasourceUid":"$expr",
     "model":{"type":"threshold","expression":"D","conditions":[{"evaluator":{"params":[0],"type":"gt"},"operator":{"type":"and"},"query":{"params":["D"]},"reducer":{"type":"last"},"type":"query"}],"refId":"C","datasource":{"type":"__expr__","uid":"$expr"},"intervalMs":1000,"maxDataPoints":43200}}
  ]
}
"@)

Write-Host "`nSemua alert rules dicipta!"
