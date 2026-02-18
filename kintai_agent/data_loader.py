"""
データローダー

CSVファイルからマスタデータを読み込む
"""

import csv
from pathlib import Path
from typing import List, Optional
from .models import Project, Category


class DataLoader:
    """マスタデータローダー"""
    
    def __init__(self, projects_path: str, categories_path: str):
        """
        初期化
        
        Args:
            projects_path: 案件マスタCSVファイルのパス
            categories_path: 区分マスタCSVファイルのパス
        """
        self.projects_path = Path(projects_path)
        self.categories_path = Path(categories_path)
        
        # データをロード
        self.projects = self._load_projects()
        self.categories = self._load_categories()
    
    def _load_projects(self) -> List[Project]:
        """
        案件マスタをロード
        
        Returns:
            案件リスト
            
        Raises:
            FileNotFoundError: ファイルが見つからない場合
            ValueError: CSVフォーマットが不正な場合
        """
        if not self.projects_path.exists():
            raise FileNotFoundError(f"案件マスタファイルが見つかりません: {self.projects_path}")
        
        projects = []
        try:
            with open(self.projects_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # 必須カラムのチェック
                if 'id' not in reader.fieldnames or 'name' not in reader.fieldnames:
                    raise ValueError("案件マスタCSVには'id'と'name'カラムが必要です")
                
                for row in reader:
                    try:
                        project = Project(
                            id=int(row['id']),
                            name=row['name'].strip()
                        )
                        projects.append(project)
                    except (ValueError, KeyError) as e:
                        raise ValueError(f"案件マスタの行の解析に失敗しました: {row}. エラー: {e}")
        
        except Exception as e:
            if isinstance(e, (FileNotFoundError, ValueError)):
                raise
            raise ValueError(f"案件マスタの読み込みに失敗しました: {e}")
        
        if not projects:
            raise ValueError("案件マスタが空です")
        
        return projects
    
    def _load_categories(self) -> List[Category]:
        """
        区分マスタをロード
        
        Returns:
            区分リスト
            
        Raises:
            FileNotFoundError: ファイルが見つからない場合
            ValueError: CSVフォーマットが不正な場合
        """
        if not self.categories_path.exists():
            raise FileNotFoundError(f"区分マスタファイルが見つかりません: {self.categories_path}")
        
        categories = []
        try:
            with open(self.categories_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # 必須カラムのチェック
                if 'id' not in reader.fieldnames or 'name' not in reader.fieldnames:
                    raise ValueError("区分マスタCSVには'id'と'name'カラムが必要です")
                
                for row in reader:
                    try:
                        category = Category(
                            id=int(row['id']),
                            name=row['name'].strip()
                        )
                        categories.append(category)
                    except (ValueError, KeyError) as e:
                        raise ValueError(f"区分マスタの行の解析に失敗しました: {row}. エラー: {e}")
        
        except Exception as e:
            if isinstance(e, (FileNotFoundError, ValueError)):
                raise
            raise ValueError(f"区分マスタの読み込みに失敗しました: {e}")
        
        if not categories:
            raise ValueError("区分マスタが空です")
        
        return categories
    
    def get_project_by_id(self, project_id: int) -> Optional[Project]:
        """
        IDで案件を取得
        
        Args:
            project_id: 案件ID
            
        Returns:
            案件、見つからない場合はNone
        """
        for project in self.projects:
            if project.id == project_id:
                return project
        return None
    
    def get_category_by_id(self, category_id: int) -> Optional[Category]:
        """
        IDで区分を取得
        
        Args:
            category_id: 区分ID
            
        Returns:
            区分、見つからない場合はNone
        """
        for category in self.categories:
            if category.id == category_id:
                return category
        return None
    
    def get_project_by_name(self, name: str) -> Optional[Project]:
        """
        名前で案件を取得（完全一致）
        
        Args:
            name: 案件名
            
        Returns:
            案件、見つからない場合はNone
        """
        for project in self.projects:
            if project.name == name:
                return project
        return None
    
    def get_category_by_name(self, name: str) -> Optional[Category]:
        """
        名前で区分を取得（完全一致）
        
        Args:
            name: 区分名
            
        Returns:
            区分、見つからない場合はNone
        """
        for category in self.categories:
            if category.name == name:
                return category
        return None
