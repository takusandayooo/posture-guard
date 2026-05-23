<div id="top"></div>

# Posture Guard

<p>
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB.svg?logo=python&style=for-the-badge&logoColor=white" alt="Python 3.11 or 3.12">
  <img src="https://img.shields.io/badge/uv-managed-2C5F2D.svg?style=for-the-badge" alt="uv managed">
  <img src="https://img.shields.io/badge/OpenCV-camera-5C3EE8.svg?logo=opencv&style=for-the-badge&logoColor=white" alt="OpenCV">
  <img src="https://img.shields.io/badge/MediaPipe-pose-0097A7.svg?style=for-the-badge" alt="MediaPipe">
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows-supported-000000.svg?style=for-the-badge" alt="macOS and Windows">
</p>

Posture Guard は、Web カメラで登録した「自分にとっての良い姿勢」からのずれを検知し、姿勢が戻らない場合に Wi-Fi オフ、画面ロック、再起動などで作業を強制中断するデスクトップアプリです。

English documentation is available in [README.en.md](README.en.md).

## 目次

1. [プロジェクトについて](#プロジェクトについて)
2. [使用技術](#使用技術)
3. [動作環境](#動作環境)
4. [ディレクトリ構成](#ディレクトリ構成)
5. [開発環境構築](#開発環境構築)
6. [使い方](#使い方)
7. [設定とコマンド](#設定とコマンド)
8. [OS 別の注意点](#os-別の注意点)
9. [姿勢判定の仕組み](#姿勢判定の仕組み)
10. [トラブルシューティング](#トラブルシューティング)
11. [開発](#開発)

## プロジェクトについて

長時間の PC 作業では、気づかないうちに背中が丸まり、首が前に出た姿勢を続けがちです。Posture Guard は、姿勢が崩れた状態を放置すると開発体験そのものが悪くなる、という強いフィードバックで姿勢を直すためのネタ寄りの姿勢監視ツールです。

このアプリは一般的な「正しい姿勢」を判定しません。起動後にユーザー自身が良い姿勢で基準姿勢を登録し、その基準からの差分を監視します。姿勢の崩れが一定時間続くと警告を出し、設定に応じて Wi-Fi オフや追加アクションを実行します。

主な特徴:

- Web カメラで Reference Posture を登録し、現在の姿勢との差分を監視
- 姿勢が崩れてもすぐには止めず、警告と猶予時間を挟んでから実行
- Wi-Fi オフ、画面ロック、再起動、何もしない、を設定可能
- Wi-Fi の復帰は自動化せず、ユーザーが手動で行う Manual Recovery 前提
- macOS と Windows に対応
- `--dry-run` で危険な操作を実行せずに挙動確認が可能

<p align="right">(<a href="#top">トップへ</a>)</p>

## 使用技術

| 種別 | 技術 | 用途 |
| --- | --- | --- |
| 言語 | Python | CLI と姿勢監視処理 |
| パッケージ管理 | uv | 依存関係の同期、実行、テスト |
| 姿勢推定 | MediaPipe | 顔、耳、肩のランドマーク検出 |
| カメラ/描画 | OpenCV | カメラ入力、画面表示、ステータス描画 |
| 数値計算 | NumPy | 姿勢特徴量、しきい値、スコア計算 |
| 設定 UI | Tkinter | 実行中に変更できる設定パネル |
| テスト | pytest | ユニットテスト、任意の Wi-Fi 結合テスト |

<p align="right">(<a href="#top">トップへ</a>)</p>

## 動作環境

| 項目 | バージョン/条件 |
| --- | --- |
| Python | 3.11 以上、3.13 未満 |
| OS | macOS または Windows |
| カメラ | OpenCV から参照できる Web カメラ |
| macOS Wi-Fi 制御 | `networksetup` が利用できること |
| Windows Wi-Fi 制御 | PowerShell の `Get-NetAdapter`、`Disable-NetAdapter`、`Enable-NetAdapter` が利用できること |

MediaPipe が新しい Python バージョン向けの wheel を提供していない場合があるため、Python は 3.11 または 3.12 を使ってください。

環境変数は通常不要です。実 Wi-Fi 制御の結合テストだけ、`POSTURE_GUARD_RUN_WIFI_INTEGRATION=1` を指定した場合に実行されます。

<p align="right">(<a href="#top">トップへ</a>)</p>

## ディレクトリ構成

```text
.
├── README.md
├── README.en.md
├── CONTEXT.md
├── pyproject.toml
├── uv.lock
├── src
│   └── posture_guard
│       ├── __init__.py
│       └── cli.py
└── tests
    ├── test_cli.py
    └── test_wifi_integration.py
```

主要ファイル:

| パス | 役割 |
| --- | --- |
| `src/posture_guard/cli.py` | CLI、姿勢監視、Wi-Fi 制御、警告、追加アクションの実装 |
| `tests/test_cli.py` | 姿勢判定、コマンド生成、設定値などのユニットテスト |
| `tests/test_wifi_integration.py` | 実 Wi-Fi をオン/オフする任意実行の結合テスト |
| `CONTEXT.md` | ドメイン用語と設計上の前提 |
| `pyproject.toml` | プロジェクト設定、依存関係、CLI エントリポイント |

<p align="right">(<a href="#top">トップへ</a>)</p>

## 開発環境構築

1. Python 3.11 または 3.12 を用意します。
2. `uv` をインストールします。
3. 依存関係を同期します。

```sh
uv sync
```

動作確認は、最初に必ず dry run で行ってください。dry run では Wi-Fi の変更、画面ロック、再起動は実行されず、実行予定のコマンドだけが表示されます。

```sh
uv run posture-guard --dry-run
```

<p align="right">(<a href="#top">トップへ</a>)</p>

## 使い方

1. アプリを起動します。
2. カメラ画面と設定ウィンドウが開きます。
3. 良い姿勢で座り、`c` を押して基準姿勢を登録します。
4. アプリが Web カメラで姿勢を監視します。
5. 姿勢が崩れると、画面に警告とカウントが表示されます。
6. 設定した秒数を超えて姿勢が戻らない場合、Wi-Fi がオフになります。
7. さらに姿勢が戻らない場合、設定に応じて画面ロック、再起動、または何もしない動作を実行します。
8. Wi-Fi はユーザーが手動でオンに戻します。

実際に Wi-Fi 制御を有効にして起動する場合:

```sh
uv run posture-guard
```

キー操作:

| キー | 操作 |
| --- | --- |
| `c` | 基準姿勢を登録、または登録し直す |
| `q` | 終了 |

設定ウィンドウで変更できる項目:

| 項目 | 内容 |
| --- | --- |
| Calibration sec | 基準姿勢を登録する秒数 |
| Deviation sec | 姿勢が崩れてから Wi-Fi をオフにするまでの秒数 |
| Grace sec | 警告後、追加アクションを実行するまでの猶予秒数 |
| Turn Wi-Fi off after deviation | 姿勢の崩れで Wi-Fi をオフにするか |
| Action | 画面ロック、再起動、何もしない、の選択 |
| Show warning popup | 警告ポップアップを表示するか |

<p align="right">(<a href="#top">トップへ</a>)</p>

## 設定とコマンド

### 実行コマンド一覧

| コマンド | 処理 |
| --- | --- |
| `uv sync` | 依存関係をインストールし、仮想環境を同期 |
| `uv run posture-guard --dry-run` | OS 操作を実行せずに姿勢監視を起動 |
| `uv run posture-guard` | Wi-Fi 制御などを有効にして姿勢監視を起動 |
| `uv run posture-guard --camera 1` | カメラインデックスを指定して起動 |
| `uv run posture-guard --wifi-device en0` | Wi-Fi デバイス名を指定して起動 |
| `uv run pytest` | テストを実行 |

### CLI オプション

| オプション | デフォルト | 内容 |
| --- | --- | --- |
| `--camera` | `0` | OpenCV のカメラインデックス |
| `--wifi-device` | `auto` | Wi-Fi デバイスまたはアダプター名 |
| `--dry-run` | `false` | OS 操作を実行せず、実行予定コマンドを表示 |
| `--calibration-seconds` | `10` | 基準姿勢の登録秒数 |
| `--deviation-seconds` | `5` | 姿勢の崩れが続いたと判定する秒数 |
| `--consequence-action` | `lock` | 猶予時間後の動作。`lock`、`reboot`、`none` |
| `--consequence-grace-seconds` | `30` | 追加アクションまでの猶予秒数 |
| `--warning-popup` | `true` | 警告ポップアップを表示 |
| `--no-warning-popup` | `false` | 警告ポップアップを非表示 |
| `--deviation-margin` | `0.15` | しきい値をどれだけ超えたらカウント開始するか |
| `--recovery-poll-seconds` | `2.0` | 手動復帰後の Wi-Fi 状態確認間隔 |

<p align="right">(<a href="#top">トップへ</a>)</p>

## OS 別の注意点

### Windows

Windows では Wi-Fi アダプターの有効化/無効化に PowerShell の `Get-NetAdapter`、`Disable-NetAdapter`、`Enable-NetAdapter` を使います。Wi-Fi を実際にオフにするには、管理者権限でターミナルを起動してください。

自動検出がうまくいかない場合は、アダプター名を指定します。

```sh
uv run posture-guard --wifi-device "Wi-Fi"
```

### macOS

macOS では Wi-Fi 制御に `networksetup` を使います。自動検出がうまくいかない場合は、デバイス名を指定します。

```sh
uv run posture-guard --wifi-device en0
```

画面ロックはディスプレイスリープ、ユーザーセッションのサスペンド、スクリーンセーバー起動、キーボードショートカットを順に試します。macOS 側で「スリープまたはスクリーンセーバ開始後にパスワードを要求」が有効になっていることを確認してください。

<p align="right">(<a href="#top">トップへ</a>)</p>

## 姿勢判定の仕組み

画面の `score / threshold` は、現在の姿勢が登録した基準姿勢からどれだけ離れているかを示します。スコアは肩の位置、肩に対する頭の位置、肩の傾きを使って計算します。

小さなカメラ位置のずれで過剰反応しないように、肩の位置は頭の位置より軽く扱います。また、`3.01 / 3.00` のようなわずかな超過では Wi-Fi オフのカウントを始めません。デフォルトでは、スコアがしきい値より 15% 高くなった時点からカウントを開始します。この値はカメラ画面に `Off starts at` として表示されます。

<p align="right">(<a href="#top">トップへ</a>)</p>

## トラブルシューティング

### `uv` がキャッシュ権限で失敗する

ホームディレクトリ配下の `uv` キャッシュにアクセスできない環境では、キャッシュ先を作業可能なディレクトリに変えて実行してください。

```sh
UV_CACHE_DIR=.uv-cache uv sync
UV_CACHE_DIR=.uv-cache uv run posture-guard --dry-run
```

### キャリブレーションに失敗する

顔、耳、両肩がカメラに入るように座り、基準姿勢を登録する秒数を長めに設定してください。1 秒などの短い設定では、必要なサンプル数が集まらないことがあります。

### カメラが開けない

OS のカメラ権限を確認し、必要に応じて `--camera` で別のカメラインデックスを指定してください。

```sh
uv run posture-guard --camera 1
```

### Wi-Fi デバイスを自動検出できない

macOS では `en0` などのデバイス名、Windows では `"Wi-Fi"` などのアダプター名を指定してください。

```sh
uv run posture-guard --wifi-device en0
uv run posture-guard --wifi-device "Wi-Fi"
```

### Windows で Wi-Fi をオフにできない

管理者権限でターミナルを起動してください。PowerShell のネットワークアダプター操作には権限が必要です。

### macOS で画面ロックされない

macOS の「スリープまたはスクリーンセーバ開始後にパスワードを要求」が有効か確認してください。環境によってはディスプレイスリープのみ実行される場合があります。

<p align="right">(<a href="#top">トップへ</a>)</p>

## 開発

通常のテスト:

```sh
uv run pytest
```

実 Wi-Fi をオン/オフする結合テスト:

```sh
POSTURE_GUARD_RUN_WIFI_INTEGRATION=1 uv run pytest tests/test_wifi_integration.py
```

この結合テストは実際に Wi-Fi を切断するため、必要な場合だけ実行してください。

<p align="right">(<a href="#top">トップへ</a>)</p>
