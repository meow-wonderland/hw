#!/bin/bash

# 清理錯誤的遊戲下載目錄

echo "========================================"
echo "  清理遊戲下載目錄"
echo "========================================"
echo ""

# 顏色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 檢查目錄
if [ ! -d "player_client" ]; then
    echo -e "${RED}錯誤：請在 hw3_game_store/hw3_game_store 目錄下執行此腳本${NC}"
    exit 1
fi

cd player_client

if [ ! -d "downloads" ]; then
    echo -e "${YELLOW}⚠ downloads 目錄不存在${NC}"
    echo "無需清理"
    exit 0
fi

echo "當前下載的遊戲："
ls -1 downloads/ 2>/dev/null || echo "  (空)"
echo ""

read -p "確定要刪除所有下載的遊戲嗎？(y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "取消操作"
    exit 0
fi

echo ""
echo "刪除中..."
rm -rf downloads/*

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 清理完成${NC}"
else
    echo -e "${RED}✗ 清理失敗${NC}"
    exit 1
fi

echo ""
echo "========================================"
echo -e "${GREEN}下一步：${NC}"
echo ""
echo "1. 啟動 Player Client:"
echo "   python3 main.py"
echo ""
echo "2. 登入帳號"
echo ""
echo "3. 進入 Store 重新下載遊戲"
echo ""
echo "4. 下載完成後可以正常創建房間和啟動遊戲"
echo ""
echo "========================================"