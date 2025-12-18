# 快速啟動指南 - Quick Start Guide

## 最快速的Demo方式

### 1. 安裝依賴
```bash
pip install customtkinter
```

### 2. 啟動伺服器
```bash
cd server
python3 main.py
```

### 3. 上傳遊戲 (新終端)
```bash
cd developer_client
python3 developer_cli.py
```
- 選擇 `2` 註冊開發者帳號（例如: `dev1`, 密碼: `dev1`）
- 選擇 `1` 登入
- 選擇 `2` 上傳遊戲
- 輸入資訊:
  ```
  Game name: Connect4
  Description: Classic Connect 4 game
  Version: 1.0.0
  Min players: 2
  Max players: 2
  Game type: gui
  Game directory path: ../example_games/connect4
  ```

### 4. 啟動玩家A (新終端)
```bash
cd player_client
python3 main.py
```
- 註冊帳號: `player1`, 密碼: `123`
- 瀏覽商城 → 下載 Connect4
- 進入大廳 → 建立房間

### 5. 啟動玩家B (新終端)
```bash
cd player_client
python3 main.py
```
- 註冊帳號: `player2`, 密碼: `123`
- 下載 Connect4
- 進入大廳 → 加入房間

### 6. 開始遊戲
- 玩家A點擊「Start Game」
- 兩個遊戲視窗自動彈出
- 開始遊玩 Connect4！

## Use Cases 驗證

✅ **D1 (上傳遊戲)**: Step 3
✅ **D2 (更新遊戲)**: Developer CLI → 選擇 `3`
✅ **D3 (下架遊戲)**: Developer CLI → 選擇 `4`
✅ **P1 (瀏覽商城)**: Player GUI → Store 頁面
✅ **P2 (下載遊戲)**: Player GUI → 點擊 Download
✅ **P3 (建立房間)**: Player GUI → Lobby → Create Room
✅ **P4 (評分留言)**: Player GUI → Game Details → Write Review

## 關卡驗證

✅ **關卡A (雙人CLI)**: Connect4 支援CLI連接
✅ **關卡B (GUI介面)**: Connect4 使用 Tkinter GUI
⚠️ **關卡C (多人)**: 框架已支援，可擴展至3+人遊戲

## 注意事項

1. **伺服器必須先啟動**才能使用客戶端
2. **遊戲需要先上傳**才能在商城中看到
3. **遊戲需要先下載**才能建立房間
4. 所有操作都有清楚的GUI提示，無需記憶指令

## 檔案位置

- 伺服器資料庫: `server/database/game_store.db`
- 上架遊戲: `server/games/{game_id}/`
- 玩家下載: `player_client/downloads/{game_name}/`
- 伺服器日誌: `server/logs/server.log`

## 疑難排解

**無法連接**: 確認伺服器已啟動，檢查防火牆
**下載失敗**: 確認遊戲已正確上傳
**遊戲無法啟動**: 確認遊戲已下載完成

---

更多詳細資訊請參考 `README.md`
