"""
Command Generator - OA Lacco APPコマンド生成と検証
"""
import re
from typing import List, Tuple
from datetime import datetime


class CommandGenerator:
    """
    OA Lacco APPコマンドの生成と検証を行うクラス
    """
    
    # コマンド形式: OA Lacco APP add YYYY/MM/DD 案件ID 区分ID 割合%
    COMMAND_PATTERN = r'^OA Lacco APP add \d{4}/\d{2}/\d{2} \d+ \d+ \d+%$'
    
    @staticmethod
    def validate_command(command: str) -> Tuple[bool, str]:
        """
        コマンド形式を検証
        
        Args:
            command: 検証するコマンド文字列
            
        Returns:
            Tuple[bool, str]: (検証結果, エラーメッセージ)
        """
        # 改行や余分な空白を削除
        command = command.strip()
        
        # 基本的な形式チェック
        if not re.match(CommandGenerator.COMMAND_PATTERN, command):
            return False, "コマンド形式が正しくありません。正しい形式: OA Lacco APP add YYYY/MM/DD 案件ID 区分ID 割合%"
        
        # コマンドをパース（"OA Lacco APP add"の後の部分を取得）
        parts = command.split()
        # OA Lacco APP add 日付 案件ID 区分ID 割合 = 8個
        if len(parts) != 8:
            return False, f"コマンドの要素数が正しくありません（{len(parts)}個、期待値: 8個）"
        
        try:
            # 日付の検証（parts[4]）
            date_str = parts[4]
            datetime.strptime(date_str, "%Y/%m/%d")
            
            # 案件IDの検証（parts[5]）
            project_id = int(parts[5])
            if project_id <= 0:
                return False, "案件IDは正の整数である必要があります"
            
            # 区分IDの検証（parts[6]）
            category_id = int(parts[6])
            if category_id <= 0:
                return False, "区分IDは正の整数である必要があります"
            
            # 割合の検証（parts[7]）
            percentage_str = parts[7].rstrip('%')
            percentage = int(percentage_str)
            if percentage < 0 or percentage > 100:
                return False, "割合は0〜100の範囲である必要があります"
            
            return True, ""
            
        except ValueError as e:
            return False, f"値の形式が正しくありません: {str(e)}"
    
    @staticmethod
    def validate_commands(commands: List[str]) -> Tuple[bool, List[str]]:
        """
        複数のコマンドを検証
        
        Args:
            commands: 検証するコマンドのリスト
            
        Returns:
            Tuple[bool, List[str]]: (全て有効か, エラーメッセージのリスト)
        """
        errors = []
        
        for i, command in enumerate(commands, 1):
            is_valid, error_msg = CommandGenerator.validate_command(command)
            if not is_valid:
                errors.append(f"コマンド{i}: {error_msg}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_percentage_total(commands: List[str]) -> Tuple[bool, str, int]:
        """
        コマンドの割合合計を検証
        
        Args:
            commands: 検証するコマンドのリスト
            
        Returns:
            Tuple[bool, str, int]: (合計が100%か, メッセージ, 合計値)
        """
        total = 0
        
        for command in commands:
            # 改行や余分な空白を削除
            command = command.strip()
            parts = command.split()
            # OA Lacco APP add 日付 案件ID 区分ID 割合 = 8個
            if len(parts) >= 8:
                percentage_str = parts[7].rstrip('%')
                try:
                    total += int(percentage_str)
                except ValueError:
                    return False, "割合の解析に失敗しました", 0
        
        if total == 100:
            return True, "割合の合計は100%です", total
        elif total < 100:
            shortage = 100 - total
            return False, f"割合の合計が{total}%です。{shortage}%不足しています", total
        else:
            excess = total - 100
            return False, f"割合の合計が{total}%です。{excess}%超過しています", total
    
    @staticmethod
    def format_command(
        date: str,
        project_id: int,
        category_id: int,
        percentage: int
    ) -> str:
        """
        コマンドを生成
        
        Args:
            date: 日付（YYYY/MM/DD形式）
            project_id: 案件ID
            category_id: 区分ID
            percentage: 割合
            
        Returns:
            str: 生成されたコマンド
        """
        return f"OA Lacco APP add {date} {project_id} {category_id} {percentage}%"
