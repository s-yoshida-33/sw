# SW Display System

## システム概要

di2osc デバイスのデジタル入力（DI）信号を OSC/UDP で受信し、対応する画像を全画面表示するシステムです。

```
di2osc デバイス
    │  DI1〜DI8 のON/OFF を OSC/UDP でブロードキャスト
    │  送信先: 255.255.255.255:9000
    ↓
表示機（view.py）
    │  /di/{n} 1 → 画像を全画面表示
    │  /di/{n} 0 → 非表示（待機状態）
    ↓
DI_View_{n}.png を全画面表示
```


## ディレクトリ構成

```
sw\
│
├─ config\
│  └─ config.txt                ← 設定ファイル（OSCポート等）
│
├─ images\                      ← 表示画像 命名規則: DI_View_{ch}.png/.jpg
│  ├─ DI_View_1.png             ← DI1  表示用画像
│  ├─ DI_View_2.png             ← DI2  表示用画像
│  ├─ DI_View_3.png             ← DI3  表示用画像
│  ├─ DI_View_4.png             ← DI4  表示用画像
│  ├─ DI_View_5.png             ← DI5  表示用画像
│  ├─ DI_View_6.png             ← DI6  表示用画像
│  ├─ DI_View_7.png             ← DI7  表示用画像
│  ├─ DI_View_8.png             ← DI8  表示用画像
│  ├─ DI_View_9.png             ← DI9  表示用画像
│  └─ DI_View_10.png            ← DI10 表示用画像
│
├─ installer\
│  ├─ ChromeSetup.exe           ← Chrome インストーラー
│  └─ python-3.10.6-amd64.exe   ← Python 3.10 Windows 64bit インストーラー
│
├─ logs\
│  └─ YYYY-MM-DD\               ← 日付ごとにフォルダが作成される
│     └─ view.log               ← 表示ログ
│
├─ view\
│  └─ view.py                   ← OSC/UDP 受信 & Tkinter 画面制御
│
├─ README.md
├─ requirements.txt             ← 必要ライブラリ
├─ start_view.bat               ← 表示アプリ 起動
└─ stop_view.bat                ← 表示アプリ 終了
```


## セットアップ

### 1. Python をインストール

`sw\installer\python-3.10.6-amd64.exe` を実行

> **必ず「Add python.exe to PATH」にチェックを入れてインストールすること**

---

### 2. sw フォルダを配置

解凍した `sw` を `C:\` 直下に配置

```
C:\sw\
```

---

### 3. ライブラリをインストール

ターミナル（管理者）を起動し、以下を実行

```
cd C:\sw
pip install -r requirements.txt
```

---

### 4. 設定ファイルを確認

`C:\sw\config\config.txt`

```
# 表示設定
OSC_PORT=9000
```

di2osc デバイス側の OSC ポートと一致していること（デフォルト: 9000）

---

### 5. 起動

```
C:\sw\start_view.bat を管理者権限で実行
```

初回起動時にスタートアップへの登録が自動で行われます。


## 停止（メンテナンス時）

```
C:\sw\stop_view.bat を実行
```

プロセスを完全に終了します。ファイルの更新や画像の差し替えはこの後に行ってください。


## 画像の差し替え

| ファイル名 | 対応チャンネル |
|-----------|--------------|
| `DI_View_1.png` | DI1 |
| `DI_View_2.png` | DI2 |
| `DI_View_3.png` | DI3 |
| `DI_View_4.png` | DI4 |
| `DI_View_5.png` | DI5 |
| `DI_View_6.png` | DI6 |
| `DI_View_7.png` | DI7 |
| `DI_View_8.png` | DI8 |

- 対応する番号のファイルを上書きするだけで反映されます
- `.jpg` 形式も使用可能です
- 差し替え前に `stop_view.bat` でプロセスを終了してください


## ログ

`C:\sw\logs\YYYY-MM-DD\view.log` に日付ごとに記録されます。

表示機は毎日午前3時に OS 再起動するよう別途タスクスケジューラで設定されており、再起動のタイミングで当日の日付フォルダが新たに作成されます。
