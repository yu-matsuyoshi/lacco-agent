/**
 * Lambda function to get categories from S3
 */

import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';

const s3Client = new S3Client({});
const BUCKET_NAME = process.env.DATA_BUCKET!;
const CATEGORIES_KEY = 'master-data/categories.csv';

interface Category {
  id: number;
  name: string;
}

export const handler = async (event: any) => {
  try {
    console.log('Fetching categories from S3:', { bucket: BUCKET_NAME, key: CATEGORIES_KEY });

    // S3からCSVファイルを取得
    const command = new GetObjectCommand({
      Bucket: BUCKET_NAME,
      Key: CATEGORIES_KEY,
    });

    const response = await s3Client.send(command);
    const csvContent = await response.Body?.transformToString();

    if (!csvContent) {
      throw new Error('Empty CSV content');
    }

    // CSVをパース（ヘッダー行をスキップ）
    const lines = csvContent.trim().split('\n');
    const categories: Category[] = [];

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      const [id, name] = line.split(',');
      categories.push({
        id: parseInt(id, 10),
        name: name.trim(),
      });
    }

    console.log(`Successfully loaded ${categories.length} categories`);

    return {
      statusCode: 200,
      body: JSON.stringify(categories),
    };
  } catch (error) {
    console.error('Error fetching categories:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({
        error: 'Failed to fetch categories',
        message: error instanceof Error ? error.message : 'Unknown error',
      }),
    };
  }
};
