"""
Command Generator - OA Lacco APPコマンド生成と検証
"""
import re
from typing import List, Tuple, Optional
from datetime import datetime


class CommandGenerator:
    """
    OA Lacco APPコマンドの生成と検証を行うクラス
    """

    # コマンドパターン定義
    PATTERNS = {
        # 単日add: OA Lacco APP add YYYY/MM/DD 案件ID 区分ID 割合%
        'add': r'^OA Lacco APP add \d{4}/\d{2}/\d{2} \d+ \d+ \d+%$',
        # 月全体add: OA Lacco APP add -r YYYY/MM 案件ID 区分ID 割合%
        'add_r': r'^OA Lacco APP add -r \d{4}/\d{2} \d+ \d+ \d+%$',
        # 日数指定add: OA Lacco APP add -t 日数 YYYY/MM/DD 案件ID 区分ID 割合%
        'add_t': r'^OA Lacco APP add -t \d+ \d{4}/\d{2}/\d{2} \d+ \d+ \d+%$',
        # 期間指定add: OA Lacco APP add -u YYYY/MM/DD YYYY/MM/DD 案件ID 区分ID 割合%
        'add_u': r'^OA Lacco APP add -u \d{4}/\d{2}/\d{2} \d{4}/\d{2}/\d{2} \d+ \d+ \d+%$',
        # コピー: OA Lacco APP cp YYYY/MM/DD YYYY/MM/DD (または .)
        'cp': r'^OA Lacco APP cp (\d{4}/\d{2}/\d{2}|\.) (\d{4}/\d{2}/\d{2}|\.)$',
        # 削除（日）: OA Lacco APP rm YYYY/MM/DD
        'rm_day': r'^OA Lacco APP rm \d{4}/\d{2}/\d{2}$',
        # 削除（月）: OA Lacco APP rm YYYY/MM
        'rm_month': r'^OA Lacco APP rm \d{4}/\d{2}$',
        # 確認（日）: OA Lacco APP ls /data/YYYY/MM/DD
        'ls_day': r'^OA Lacco APP ls /data/\d{4}/\d{2}/\d{2}$',
        # 確認（月）: OA Lacco APP ls /data/YYYY/MM
        'ls_month': r'^OA Lacco APP ls /data/\d{4}/\d{2}$',
        # 確認（今月）: OA Lacco APP ls now
        'ls_now': r'^OA Lacco APP ls now$',
    }

    # 後方互換性のため残す
    COMMAND_PATTERN = PATTERNS['add']
    
    @classmethod
    def get_command_type(cls, command: str) -> Optional[str]:
        """
        コマンドの種類を判定

        Args:
            command: コマンド文字列

        Returns:
            コマンドタイプ（add, add_r, cp, rm_day, ls_now等）またはNone
        """
        command = command.strip()
        for cmd_type, pattern in cls.PATTERNS.items():
            if re.match(pattern, command):
                return cmd_type
        return None

    @classmethod
    def validate_command(cls, command: str) -> Tuple[bool, str]:
        """
        コマンド形式を検証

        Args:
            command: 検証するコマンド文字列

        Returns:
            Tuple[bool, str]: (検証結果, エラーメッセージ)
        """
        command = command.strip()
        cmd_type = cls.get_command_type(command)

        if cmd_type is None:
            return False, "コマンド形式が正しくありません。対応コマンド: add, add -r/-t/-u, cp, rm, ls"

        parts = command.split()

        try:
            # コマンドタイプごとの検証
            if cmd_type == 'add':
                return cls._validate_add(parts)
            elif cmd_type == 'add_r':
                return cls._validate_add_r(parts)
            elif cmd_type == 'add_t':
                return cls._validate_add_t(parts)
            elif cmd_type == 'add_u':
                return cls._validate_add_u(parts)
            elif cmd_type == 'cp':
                return cls._validate_cp(parts)
            elif cmd_type in ('rm_day', 'rm_month'):
                return cls._validate_rm(parts, cmd_type)
            elif cmd_type in ('ls_day', 'ls_month', 'ls_now'):
                return True, ""  # lsコマンドはパターンマッチで十分

            return True, ""

        except ValueError as e:
            return False, f"値の形式が正しくありません: {str(e)}"

    @staticmethod
    def _validate_add(parts: List[str]) -> Tuple[bool, str]:
        """単日addコマンドの検証"""
        # OA Lacco APP add 日付 案件ID 区分ID 割合 = 8個
        if len(parts) != 8:
            return False, f"コマンドの要素数が正しくありません（{len(parts)}個、期待値: 8個）"

        datetime.strptime(parts[4], "%Y/%m/%d")

        project_id = int(parts[5])
        if project_id <= 0:
            return False, "案件IDは正の整数である必要があります"

        category_id = int(parts[6])
        if category_id <= 0:
            return False, "区分IDは正の整数である必要があります"

        percentage = int(parts[7].rstrip('%'))
        if percentage < 0 or percentage > 100:
            return False, "割合は0〜100の範囲である必要があります"

        return True, ""

    @staticmethod
    def _validate_add_r(parts: List[str]) -> Tuple[bool, str]:
        """月全体addコマンドの検証"""
        # OA Lacco APP add -r 年月 案件ID 区分ID 割合 = 9個
        if len(parts) != 9:
            return False, f"コマンドの要素数が正しくありません（{len(parts)}個、期待値: 9個）"

        datetime.strptime(parts[5] + "/01", "%Y/%m/%d")  # 年月の検証

        project_id = int(parts[6])
        if project_id <= 0:
            return False, "案件IDは正の整数である必要があります"

        category_id = int(parts[7])
        if category_id <= 0:
            return False, "区分IDは正の整数である必要があります"

        percentage = int(parts[8].rstrip('%'))
        if percentage < 0 or percentage > 100:
            return False, "割合は0〜100の範囲である必要があります"

        return True, ""

    @staticmethod
    def _validate_add_t(parts: List[str]) -> Tuple[bool, str]:
        """日数指定addコマンドの検証"""
        # OA Lacco APP add -t 日数 日付 案件ID 区分ID 割合 = 10個
        if len(parts) != 10:
            return False, f"コマンドの要素数が正しくありません（{len(parts)}個、期待値: 10個）"

        days = int(parts[5])
        if days < 2 or days > 20:
            return False, "繰り返し日数は2〜20の範囲である必要があります"

        datetime.strptime(parts[6], "%Y/%m/%d")

        project_id = int(parts[7])
        if project_id <= 0:
            return False, "案件IDは正の整数である必要があります"

        category_id = int(parts[8])
        if category_id <= 0:
            return False, "区分IDは正の整数である必要があります"

        percentage = int(parts[9].rstrip('%'))
        if percentage < 0 or percentage > 100:
            return False, "割合は0〜100の範囲である必要があります"

        return True, ""

    @staticmethod
    def _validate_add_u(parts: List[str]) -> Tuple[bool, str]:
        """期間指定addコマンドの検証"""
        # OA Lacco APP add -u 終了日 開始日 案件ID 区分ID 割合 = 10個
        if len(parts) != 10:
            return False, f"コマンドの要素数が正しくありません（{len(parts)}個、期待値: 10個）"

        end_date = datetime.strptime(parts[5], "%Y/%m/%d")
        start_date = datetime.strptime(parts[6], "%Y/%m/%d")

        if end_date < start_date:
            return False, "終了日は開始日以降である必要があります"

        project_id = int(parts[7])
        if project_id <= 0:
            return False, "案件IDは正の整数である必要があります"

        category_id = int(parts[8])
        if category_id <= 0:
            return False, "区分IDは正の整数である必要があります"

        percentage = int(parts[9].rstrip('%'))
        if percentage < 0 or percentage > 100:
            return False, "割合は0〜100の範囲である必要があります"

        return True, ""

    @staticmethod
    def _validate_cp(parts: List[str]) -> Tuple[bool, str]:
        """コピーコマンドの検証"""
        # OA Lacco APP cp 元日付 先日付 = 6個
        if len(parts) != 6:
            return False, f"コマンドの要素数が正しくありません（{len(parts)}個、期待値: 6個）"

        # 日付または . の検証
        for date_str in [parts[4], parts[5]]:
            if date_str != '.':
                datetime.strptime(date_str, "%Y/%m/%d")

        return True, ""

    @staticmethod
    def _validate_rm(parts: List[str], cmd_type: str) -> Tuple[bool, str]:
        """削除コマンドの検証"""
        # OA Lacco APP rm 日付/年月 = 5個
        if len(parts) != 5:
            return False, f"コマンドの要素数が正しくありません（{len(parts)}個、期待値: 5個）"

        if cmd_type == 'rm_day':
            datetime.strptime(parts[4], "%Y/%m/%d")
        else:  # rm_month
            datetime.strptime(parts[4] + "/01", "%Y/%m/%d")

        return True, ""
    
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
    
    @classmethod
    def validate_percentage_total(cls, commands: List[str]) -> Tuple[bool, str, int]:
        """
        コマンドの割合合計を検証

        Args:
            commands: 検証するコマンドのリスト

        Returns:
            Tuple[bool, str, int]: (合計が100%か, メッセージ, 合計値)
        """
        total = 0

        for command in commands:
            command = command.strip()
            cmd_type = cls.get_command_type(command)

            # addコマンドのみ割合を計算
            if cmd_type is None or not cmd_type.startswith('add'):
                continue

            parts = command.split()
            try:
                # コマンドタイプごとに割合の位置が異なる
                if cmd_type == 'add':
                    # OA Lacco APP add 日付 案件ID 区分ID 割合 = 8個、割合はparts[7]
                    percentage_str = parts[7].rstrip('%')
                elif cmd_type == 'add_r':
                    # OA Lacco APP add -r 年月 案件ID 区分ID 割合 = 9個、割合はparts[8]
                    percentage_str = parts[8].rstrip('%')
                elif cmd_type in ('add_t', 'add_u'):
                    # OA Lacco APP add -t/-u ... 割合 = 10個、割合はparts[9]
                    percentage_str = parts[9].rstrip('%')
                else:
                    continue

                total += int(percentage_str)
            except (ValueError, IndexError):
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
        単日addコマンドを生成

        Args:
            date: 日付（YYYY/MM/DD形式）
            project_id: 案件ID
            category_id: 区分ID
            percentage: 割合

        Returns:
            str: 生成されたコマンド
        """
        return f"OA Lacco APP add {date} {project_id} {category_id} {percentage}%"

    @staticmethod
    def format_add_monthly(
        year_month: str,
        project_id: int,
        category_id: int,
        percentage: int
    ) -> str:
        """月全体addコマンドを生成"""
        return f"OA Lacco APP add -r {year_month} {project_id} {category_id} {percentage}%"

    @staticmethod
    def format_add_days(
        days: int,
        date: str,
        project_id: int,
        category_id: int,
        percentage: int
    ) -> str:
        """日数指定addコマンドを生成"""
        return f"OA Lacco APP add -t {days} {date} {project_id} {category_id} {percentage}%"

    @staticmethod
    def format_add_until(
        end_date: str,
        start_date: str,
        project_id: int,
        category_id: int,
        percentage: int
    ) -> str:
        """期間指定addコマンドを生成"""
        return f"OA Lacco APP add -u {end_date} {start_date} {project_id} {category_id} {percentage}%"

    @staticmethod
    def format_copy(source_date: str, target_date: str) -> str:
        """コピーコマンドを生成"""
        return f"OA Lacco APP cp {source_date} {target_date}"

    @staticmethod
    def format_remove(date_or_month: str) -> str:
        """削除コマンドを生成"""
        return f"OA Lacco APP rm {date_or_month}"

    @staticmethod
    def format_list(path: str = "now") -> str:
        """確認コマンドを生成"""
        if path == "now":
            return "OA Lacco APP ls now"
        return f"OA Lacco APP ls /data/{path}"
