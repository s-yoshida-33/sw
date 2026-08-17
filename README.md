# ディレクトリ構成

```
sw\
│
├─ config\
│  ├─ config.txt                                    ← view.py / signal_logger.py 設定
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
├─ server\
│  ├─ signal_logger.py                              ← サーバー側 DI信号履歴ロガー
│  └─ requirements.txt                              ← signal_logger.py 用ライブラリ
│
├─ view\
│  ├─ view.py                                       ← STB側 Tkinter画面制御
│  └─ requirements.txt                              ← view.py 用ライブラリ
│
├─ README.md                                        ← セットアップメモ
├─ start_system.ps1                                 ← MQTT ブローカー 起動・タスク登録ファイル
├─ stop_system.ps1                                  ← MQTT ブローカー 停止ファイル
├─ start_view.ps1                                   ← Tkinter アプリ 起動・タスク登録ファイル
└─ stop_view.ps1                                    ← Tkinter アプリ 停止ファイル
```

# 仕様

## システム概要

KC868-A16 の DI（デジタル入力）チャンネルの ON/OFF を MQTT 経由でサーバー PC の Mosquitto ブローカーに送信し、STB（Windows PC）側の `view.py` がそれを購読して、対応する画像をフルスクリーン表示する。

画像表示中は STB の音声出力をミュートする。

- サーバー側：Mosquitto（MQTT ブローカー）、`signal_logger.py`（DI信号履歴のログ記録）
- STB側：`view.py`（Tkinter によるフルスクリーン画像表示 + 音声ミュート制御）
- KC868-A16：DI 信号を MQTT で送信するハードウェア

## MQTT仕様

- Broker / Port / Topic は `config\config.txt` で指定（既定値は `view.py` 内のデフォルト値）
- Payload 形式（`view.py` の `parse_di_index` で解釈）
  - `ON [DI-<番号>]` または `<番号>` の数値のみ → 該当chをON
  - `OFF`（大文字小文字区別なし）→ OFF
- 接続できない場合は5秒間隔でリトライを続ける
- チャンネル数に上限はない（画像ファイルの命名規則に依存）

## 画像表示仕様

- `images\DI_View_<番号>.png` または `.jpg` を配置すると、該当chがONになった際に自動でフルスクリーン表示される
- 対応する画像が存在しない場合は黒背景に "No Image" と表示
- OFFになるとウィンドウを非表示にする
- 同じON状態のまま別のchにON信号が切り替わった場合（ON→ON）も画像を再読み込みして表示を切り替える

## 音声ミュート仕様

画像表示中（ON）は、外部アプリ（サイネージ配信アプリ等）が再生している音声も含めて、STBのシステム音声を確実にミュートする。

- OS のミュートフラグだけでなく、マスターボリュームのレベル自体を0にする（一部のリモート音声キャプチャ経路ではミュートフラグのみでは音声が止まらないことがあるため）
- その時点で有効な（Active状態の）音声出力デバイスすべてに対して適用する（オンボードのスピーカーと、HDMI接続ディスプレイのスピーカーなど、複数デバイスが同時に有効な場合を考慮）
- OFFに戻ると、ミュート前の音量にデバイスごとに復元する
- ON→ON（別chへの切り替え）では二重にミュート処理をせず、最初にミュートした際の音量のみを保存・復元に使う

## 自動起動・タスクスケジューラ仕様

`start_system.ps1` / `start_view.ps1` を実行すると、以下のタスクがタスクスケジューラに登録され、以降は自動起動する。`start_system.ps1`側の3タスクは実行するたびに内容を検証して上書き登録するため、スクリプトの内容が変わった場合も再実行するだけで既存サーバーのタスクが最新化される（`DisplayViewerAutoStart`は既に登録済みの場合はスキップ）。

| タスク名 | トリガー | 実行アカウント | 内容 |
|---|---|---|---|
| `MosquittoAutoStart` | システム起動時 | SYSTEM | Mosquitto を起動 |
| `SignalLoggerAutoStart` | システム起動時 | SYSTEM | `signal_logger.py` を起動 |
| `SrvDailyRestart` | 毎日 03:00 | SYSTEM | サーバーPCを再起動 |
| `DisplayViewerAutoStart` | ログオン時 | 実行ユーザー | `view.py` を起動 |

停止する場合は `stop_system.ps1`（Mosquitto・`signal_logger.py`停止）、`stop_view.ps1`（`view.py`停止）を実行する。

## ログ仕様

- `view.py`：`logs\view-<yyyy-mm-dd>.log` に日付ごとにINFO/ERRORレベルで出力（信号変化、MQTT接続状況、画像読み込み・音声制御のエラーなど）
  - `view.py` 起動時（STBは信号機アプリのタスクにより毎日AM3時に再起動）に、当月以外の日別ログを月単位（`logs\<yyyy-mm>.zip`）にまとめて元ファイルを削除し、作成から12か月を超えたzipを削除する
- `signal_logger.py`：`logs\signal-<yyyy-mm-dd>.log` に日付ごとにINFO/ERRORレベルで出力（信号変化、MQTT接続状況など。STBに依存せずサーバー単体で信号履歴を確認できる。`view-*.log`と同様の月次zip化・12か月保持を行う）
- Mosquitto：`logs\mqtt.log` にエラーログのみ出力（`config\mosquitto.conf` の `log_type error` 設定による）

## 設定ファイル仕様

- `config\config.txt`：`MQTT_BROKER`, `MQTT_PORT`, `MQTT_TOPIC` を指定（`signal_logger.py`は`MQTT_PORT`, `MQTT_TOPIC`のみ使用し、ブローカーは常に自ホスト`127.0.0.1`に接続）
- `config\mosquitto.conf`：リスナーポート（既定 1883、全インターフェースで待受）、匿名接続許可、ログ出力先を指定

# セットアップ

## 1. 共通（インストール）

1-1. Google Chrome をインストール

sw\installer\ChromeSetup.exe を実行

## 2. サーバーサイド

2-1. 解凍した sw を C:\ に配置

2-2. Mosquitto をインストール

sw\installer\mosquitto-2.0.22-install-windows-x86.exe を実行

2-3. Python をインストール（`signal_logger.py` 用）

sw\installer\python-3.10.6-amd64.exe を実行

> 必ず **「Add python.exe to PATH」(PATH に追加)** にチェックを入れてインストール

2-4. ライブラリをインストール

`cd C:\sw\server && pip install -r requirements.txt`

2-5. MQTT ブローカー・signal_logger を起動

管理者権限の PowerShell で以下を実行（初回はタスクスケジューラに自動起動タスク "MosquittoAutoStart"・"SignalLoggerAutoStart" と、毎日3時の再起動タスク "SrvDailyRestart" を登録し、そのまま Mosquitto と `signal_logger.py` を起動する）

```
cd C:\sw
powershell -ExecutionPolicy Bypass -File .\start_system.ps1
```

## 3. STBサイド

3-1. 解凍したフォルダ sw を C:\ に配置

3-2. Python をインストール

sw\installer\python-3.10.6-amd64.exe を実行

> 必ず **「Add python.exe to PATH」(PATH に追加)** にチェックを入れてインストール

3-3. ターミナル（管理者）を起動

3-4. ライブラリをインストール

`cd C:\sw\view && pip install -r requirements.txt`

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
