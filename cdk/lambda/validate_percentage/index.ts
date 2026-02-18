/**
 * Lambda function to validate percentage totals
 */

interface WorkEntry {
  date: string;
  project_id: number;
  project_name: string;
  category_id: number;
  category_name: string;
  percentage: number;
}

interface ValidationResult {
  valid: boolean;
  total_percentage: number;
  errors: string[];
  warnings: string[];
}

export const handler = async (event: any) => {
  try {
    console.log('Validating percentages:', event);

    // イベントからentriesを取得
    const entries: WorkEntry[] = event.entries || [];

    if (entries.length === 0) {
      return {
        statusCode: 400,
        body: JSON.stringify({
          error: 'No entries provided',
        }),
      };
    }

    // 合計割合を計算
    const totalPercentage = entries.reduce((sum, entry) => sum + entry.percentage, 0);

    const errors: string[] = [];
    const warnings: string[] = [];

    // 検証ロジック
    if (totalPercentage === 100) {
      // 合計が100%の場合は成功
      console.log('Validation successful: total is 100%');
    } else if (totalPercentage < 100) {
      // 合計が100%未満の場合は警告
      const shortage = 100 - totalPercentage;
      warnings.push(`合計割合が${totalPercentage}%で、${shortage}%不足しています。`);
      warnings.push(`不足分を社内業務として割り当てることを検討してください。`);
    } else {
      // 合計が100%超過の場合はエラー
      const excess = totalPercentage - 100;
      errors.push(`合計割合が${totalPercentage}%で、${excess}%超過しています。`);
      errors.push(`各案件の割合を調整してください。`);
    }

    const result: ValidationResult = {
      valid: totalPercentage === 100,
      total_percentage: totalPercentage,
      errors,
      warnings,
    };

    console.log('Validation result:', result);

    return {
      statusCode: 200,
      body: JSON.stringify(result),
    };
  } catch (error) {
    console.error('Error validating percentages:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({
        error: 'Failed to validate percentages',
        message: error instanceof Error ? error.message : 'Unknown error',
      }),
    };
  }
};
