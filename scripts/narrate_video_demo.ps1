param([Parameter(Mandatory=$true)][string]$ReportPath, [Parameter(Mandatory=$true)][string]$AudioDirectory)
$ErrorActionPreference='Stop'
$demoReport=Get-Content -LiteralPath $ReportPath -Raw -Encoding utf8 | ConvertFrom-Json
$demoVoice=New-Object -ComObject SAPI.SpVoice
$portugueseFound=$false
foreach($installedVoice in $demoVoice.GetVoices()) {
    if($installedVoice.GetDescription() -match 'Portuguese\(Brazil\)') {
        $demoVoice.Voice=$installedVoice
        $portugueseFound=$true
        break
    }
}
if(-not $portugueseFound){throw 'Voz local em português indisponível; não será atribuída narração fictícia ao agente.'}
$demoVoice.Rate=0
$demoVoice.Volume=100
New-Item -ItemType Directory -Path $AudioDirectory -Force | Out-Null
foreach($demoChapter in $demoReport.chapters) {
    $waveFile=Join-Path $AudioDirectory ($demoChapter.id+'.wav')
    $speechFile=New-Object -ComObject SAPI.SpFileStream
    $speechFile.Format.Type=22
    $speechFile.Open($waveFile,3,$false)
    $demoVoice.AudioOutputStream=$speechFile
    $null=$demoVoice.Speak([string]$demoChapter.narration)
    $speechFile.Close()
    Write-Output ('Narrado: '+$demoChapter.id)
}
Write-Output ('Voz editorial: '+$demoVoice.Voice.GetDescription())
