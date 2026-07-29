# ディレクトリ構成

```
sw\
│
├─ config\
│  ├─ config.txt                                    ← view.py 設定
│  └─ mosquitto.conf                                ← Mosquitto 設定
│
├─ images\                                          ← 命名規則 [DI_View_(ch).png/.jpg]
│  │                                                  ※ch番号に上限なし
│  │                                                  ※DI_View_(ch)の画像を配置すれば、そのchの信号がONになった際に自動で表示される
│  ├─ DI_View_1.png                                 ← DI-1 表示用画像
│  ├─ DI_View_2.png                                 ← DI-2 表示用画像
│  ├─ DI_View_3.png                                 ← DI-3 表示用画像
│  ├─ ...
│  └─ DI_View_16.png                                ← DI-16 表示用画像（KC868-A16は16ch）
│
├─ installer\
│  ├─ ChromeSetup.exe                               ← Chrome インストーラー
│  ├─ mosquitto-2.0.22-install-windows-x86.exe      ← MQTT ブローカー Mosquitto インストーラー
│  └─ python-3.10.6-amd64.exe                       ← Python 3.10 Windows 64bit インストーラー
│
├─ logs\                                            ← 各ログファイル保存
│
├─ view\
│  └─ view.py                                       ← STB側 Tkinter画面制御
│
├─ README.md                                        ← セットアップメモ
├─ requirements.txt                                 ← 必要ライブラリ
├─ start_system.ps1                                 ← MQTT ブローカー 起動・タスク登録ファイル
├─ stop_system.ps1                                  ← MQTT ブローカー 停止ファイル
├─ start_view.ps1                                   ← Tkinter アプリ 起動・タスク登録ファイル
└─ stop_view.ps1                                    ← Tkinter アプリ 停止ファイル
```

# セットアップ

## 1. 共通（インストール）

1-1. Google Chrome をインストール

sw\installer\ChromeSetup.exe を実行

## 2. サーバーサイド

2-1. 解凍した sw を C:\ に配置

2-2. Mosquitto をインストール

sw\installer\mosquitto-2.0.22-install-windows-x86.exe を実行

2-3. MQTT ブローカー を起動

管理者権限の PowerShell で以下を実行（初回はタスクスケジューラに自動起動タスク "MosquittoAutoStart" と、毎日3時の再起動タスク "SrvDailyRestart" を登録し、そのまま Mosquitto を起動する）

```
cd C:\sw
powershell -ExecutionPolicy Bypass -File .\start_system.ps1
```

## 3. STBサイド

3-1. 解凍したフォルダ sw を C:\ に配置

3-2. Python をインストール

sw\installer\python-3.10.6-amd64.exe を実行

必ず「Add python.exe to PATH」(PATH に追加) にチェックを入れてインストール

3-3. ターミナル（管理者）を起動

3-4. ライブラリをインストール

`cd C:\sw && pip install -r requirements.txt`

3-5. 設定ファイルを変更

sw\config\config.txt の `MQTT_BROKER`, `MQTT_TOPIC` を変更
```
#suzaka
MQTT_BROKER=192.168.11.105
MQTT_TOPIC=kc868a16/di

#sendaikamisugi
MQTT_BROKER=192.168.11.106
MQTT_TOPIC=kc868a16/di
```

3-6. Tkinter アプリ を起動

管理者権限の PowerShell で以下を実行（初回はタスクスケジューラに自動起動タスク "DisplayViewerAutoStart"（ログオン時起動）を登録し、そのまま Tkinter アプリを起動する）

```
cd C:\sw
powershell -ExecutionPolicy Bypass -File .\start_view.ps1
```
