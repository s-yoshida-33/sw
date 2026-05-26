#ディレクトリ構成
sw\
│
├─ config\
│  ├─ config.txt                                    ← srv.py & view.py 設定
│  └─ mosquitto.conf                                ← Mosquitto 設定
│
├─ html\
│  ├─ index.html                                    ← CMS 表示用 HTML
│  └─ monitor.html                                  ← CMS 表示用 HTML
│
├─ images\                                          ← 命名規則 [DI_View_(ch).png/.jpg]
│  ├─ DI_View_0.png                                 ← DI-0 表示用画像
│  ├─ DI_View_1.png                                 ← DI-1 表示用画像
│  ├─ DI_View_2.png                                 ← DI-2 表示用画像
│  ├─ DI_View_3.png                                 ← DI-3 表示用画像
│  ├─ DI_View_4.png                                 ← DI-4 表示用画像
│  ├─ DI_View_5.png                                 ← DI-5 表示用画像
│  ├─ DI_View_6.png                                 ← DI-6 表示用画像
│  └─ DI_View_7.png                                 ← DI-7 表示用画像
│
├─ installer\
│  ├─ Advantech_IO_module_Utility_V2.7.02.msi       ← ADAM-6250 IO ユーティリティ
│  ├─ ChromeSetup.exe                               ← Chrome インストーラー
│  ├─ mosquitto-2.0.22-install-windows-x86.exe      ← MQTT ブローカー Mosquitto インストーラー
│  └─ python-3.10.6-amd64.exe                       ← Python 3.10 Windows 64bit インストーラー
│
├─ logs\                                            ← 各ログファイル保存
│
├─ server\
│  └─ srv.py                                        ← ADAM-6250 監視 & MQTT Publish
│
├─ view\
│  └─ view.py                                       ← STB側 Tkinter画面制御
│
├─ README.md                                        ← セットアップメモ
├─ requirements.txt                                 ← 必要ライブラリ
├─ start_system.bat                                 ← MQTT ブローカー & サーバー 起動ファイル
└─ start_view.bat                                   ← Tkinter アプリ 起動ファイル


#セットアップ
------------------------
1. 共通（インストール）
------------------------
1-1. Google Chrome をインストール
sw\installer\ChromeSetup.exe を実行

1-2. Python をインストール
sw\installer\python-3.10.6-amd64.exe を実行
必ず「Add python.exe to PATH」(PATH に追加) にチェックを入れてインストール

------------------------
2. サーバーサイド
------------------------
2-1. 解凍した sw を C:\ に配置

2-2. Mosquitto をインストール
sw\installer\mosquitto-2.0.22-install-windows-x86.exe を実行

2-3. ターミナル（管理者）を起動

2-4. ライブラリをインストール
`cd C:\sw && pip install -r requirements.txt`

2-5. 設定ファイルを変更
sw\config\config.txt `ADAM_IP`,`MQTT_BROKER`
#suzaka
ADAM_IP=192.168.11.104
MQTT_BROKER=192.168.11.105
#kamisugi
ADAM_IP=192.168.11.105
MQTT_BROKER=192.168.11.106

2-6. MQTT ブローカー & サーバー を起動
sw\start_system.bat を管理者権限で実行

------------------------
3. STBサイド
------------------------
3-1. 解凍したフォルダ sw を C:\ に配置

3-2. ターミナル（管理者）を起動

3-3. ライブラリをインストール
`cd C:\sw && pip install -r requirements.txt`

3-4. 設定ファイルを変更
sw\config\config.txt `ADAM_IP`,`MQTT_BROKER`
#suzaka
ADAM_IP=192.168.11.104
MQTT_BROKER=192.168.11.105
#kamisugi
ADAM_IP=192.168.11.105
MQTT_BROKER=192.168.11.106

3-5. Tkinter アプリ を起動
sw\start_view.bat を管理者権限で実行