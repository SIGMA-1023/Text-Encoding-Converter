# UST Text Encoding Converter

**Languages:** [中文](#中文) | [日本語](#日本語) | [English](#english)

---

## 中文

### 项目介绍

UST Text Encoding Converter 是一个 Windows GUI 工具，用于将日文文本文件重新保存为 **UTF-8（无 BOM）**。

本软件不会解析 UST 文件，不会修改文本内容，也不会改变任何字符。它只进行文件编码转换，并尽可能保持原始文本内容完全一致。

### 功能介绍

- 使用 PySide6 开发，界面适配 Windows 10 / Windows 11
- 支持拖拽文件和文件夹
- 支持单个文件、多个文件、单个文件夹、多个文件夹
- 支持递归扫描子文件夹
- 默认支持扩展名：`.ust`, `.txt`, `.ini`, `.cfg`, `.csv`, `.xml`, `.json`, `.yaml`, `.yml`, `.fx`, `.shader`, `.hlsl`, `.cg`, `.c`, `.cpp`, `.h`, `.cs`, `.lua`, `.py`, `.js`, `.ts`, `.html`, `.css`, `.md`
- 可在 GUI 中修改扩展名列表
- 自动按以下顺序识别编码：UTF-8, UTF-8 with BOM, CP932, Shift_JIS
- 所有转换后的文件均保存为 UTF-8 无 BOM
- 可保留原始换行符
- 保留空格、Tab、缩进、注释和最后一行状态
- 已经是 UTF-8 无 BOM 的文件会自动跳过
- 可移除 UTF-8 BOM
- 支持自动备份：`file.ust.bak`, `file.ust.bak1`, `file.ust.bak2`
- 可保留文件修改时间、访问时间和 Windows 创建时间
- 支持覆盖原文件或输出到指定目录
- 输出到指定目录时会保持原始目录结构
- 实时日志显示
- 支持复制日志和保存日志
- 显示转换进度、百分比和文件数量
- 使用后台线程处理，转换大量文件时 GUI 不会卡死
- 单个文件失败不会中断整个任务

### 重要说明

本软件只用于安全地重新编码文本文件。

严禁进行以下操作：删除空格、修改 Tab、修改缩进、增加或删除最后一行、修改注释、解析或重写 UST 内容、修改任何文本字符。

软件只允许修改文件编码。

### 环境要求

- Windows 10 或 Windows 11
- Python 3.12+
- PySide6

安装依赖：

```powershell
pip install -r requirements.txt
```

运行：

```powershell
python main.py
```

打包 EXE：

```powershell
pip install pyinstaller
pyinstaller -F -w main.py
```

生成的文件会在 `dist` 目录中。

### 项目结构

```text
.
|-- main.py
|-- requirements.txt
`-- README.md
```

### 作者

SIGMA_1023

---

## 日本語

### プロジェクト概要

UST Text Encoding Converter は、日本語テキストファイルを **UTF-8（BOM なし）** として保存し直すための Windows GUI ツールです。

このソフトウェアは UST ファイルを解析しません。テキスト内容を編集せず、文字も変更しません。行うのはファイルの文字コード変換のみで、デコード後のテキスト内容をできる限り完全に保持します。

### 機能

- PySide6 による Windows 10 / Windows 11 向け GUI
- ファイルとフォルダーのドラッグ＆ドロップに対応
- 単一ファイル、複数ファイル、単一フォルダー、複数フォルダーに対応
- サブフォルダーの再帰スキャンに対応
- デフォルト対応拡張子：`.ust`, `.txt`, `.ini`, `.cfg`, `.csv`, `.xml`, `.json`, `.yaml`, `.yml`, `.fx`, `.shader`, `.hlsl`, `.cg`, `.c`, `.cpp`, `.h`, `.cs`, `.lua`, `.py`, `.js`, `.ts`, `.html`, `.css`, `.md`
- GUI 上で拡張子リストを編集可能
- 以下の順序で文字コードを自動判定：UTF-8, UTF-8 with BOM, CP932, Shift_JIS
- 変換後のファイルはすべて UTF-8 BOM なしで保存
- 元の改行コードを保持可能
- 空白、Tab、インデント、コメント、最終行の状態を保持
- すでに UTF-8 BOM なしのファイルは自動的にスキップ
- UTF-8 BOM の除去に対応
- 自動バックアップに対応：`file.ust.bak`, `file.ust.bak1`, `file.ust.bak2`
- 更新日時、アクセス日時、Windows の作成日時を保持可能
- 元ファイルを上書き、または指定フォルダーへ出力可能
- 指定フォルダーへ出力する場合、元のフォルダー構造を保持
- リアルタイムログ表示
- ログのコピーと保存に対応
- 進捗率と処理ファイル数を表示
- バックグラウンドスレッドで処理するため、大量のファイルでも GUI が固まりません
- 1 つのファイルで失敗しても、他のファイルの処理を継続します

### 重要な注意

このソフトウェアは、安全なテキスト再エンコードのためのツールです。

以下の操作は行いません：空白の削除、Tab の変更、インデントの変更、最終行の追加または削除、コメントの変更、UST 内容の解析または再構築、任意の文字の変更。

変更されるのはファイルの文字コードのみです。

### 必要環境

- Windows 10 または Windows 11
- Python 3.12+
- PySide6

依存関係のインストール：

```powershell
pip install -r requirements.txt
```

実行：

```powershell
python main.py
```

EXE のビルド：

```powershell
pip install pyinstaller
pyinstaller -F -w main.py
```

生成された実行ファイルは `dist` フォルダーに出力されます。

### プロジェクト構成

```text
.
|-- main.py
|-- requirements.txt
`-- README.md
```

### 作者

SIGMA_1023

---

## English

### Project Overview

UST Text Encoding Converter is a Windows GUI tool for re-saving Japanese text files as **UTF-8 without BOM**.

The program does not parse UST files, does not edit text content, and does not modify any characters. It only changes the file encoding while keeping the decoded text content intact.

### Features

- Windows 10 / Windows 11 GUI built with PySide6
- Drag and drop support for files and folders
- Supports single files, multiple files, single folders, and multiple folders
- Recursive folder scanning
- Default supported extensions: `.ust`, `.txt`, `.ini`, `.cfg`, `.csv`, `.xml`, `.json`, `.yaml`, `.yml`, `.fx`, `.shader`, `.hlsl`, `.cg`, `.c`, `.cpp`, `.h`, `.cs`, `.lua`, `.py`, `.js`, `.ts`, `.html`, `.css`, `.md`
- Editable extension list in the GUI
- Automatic encoding detection in this order: UTF-8, UTF-8 with BOM, CP932, Shift_JIS
- Saves all converted files as UTF-8 without BOM
- Can preserve the original newline style
- Preserves spaces, tabs, indentation, comments, and final newline state
- Skips files that are already UTF-8 without BOM
- Can remove UTF-8 BOM
- Optional automatic backups: `file.ust.bak`, `file.ust.bak1`, `file.ust.bak2`
- Can preserve modified time, access time, and Windows creation time
- Supports overwriting original files or outputting to a selected directory
- Keeps the original folder structure when using an output directory
- Real-time log display
- Copy log and save log support
- Progress display with percentage and file count
- Background processing with `QThread`, so the GUI stays responsive
- Per-file error handling, so one failed file does not stop the whole batch

### Important Notes

This application is designed for safe text re-encoding.

It must not delete spaces, modify tabs, change indentation, add or remove the last line, change comments, parse or rewrite UST content, or modify any text character.

Only the file encoding is changed.

### Requirements

- Windows 10 or Windows 11
- Python 3.12+
- PySide6

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run:

```powershell
python main.py
```

Build EXE:

```powershell
pip install pyinstaller
pyinstaller -F -w main.py
```

The generated executable will be placed in the `dist` directory.

### Project Structure

```text
.
|-- main.py
|-- requirements.txt
`-- README.md
```

### Author

SIGMA_1023

---

## License

No license has been specified yet.
