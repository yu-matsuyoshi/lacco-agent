/**
 * Lambda function to get projects from S3
 */

import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';

const s3Client = new S3Client({});
const BUCKET_NAME = process.env.DATA_BUCKET!;
const PROJECTS_KEY = 'master-data/projects.csv';

interface Project {
  id: number;
  name: string;
}

export const handler = async (event: any) => {
  try {
    console.log('Fetching projects from S3:', { bucket: BUCKET_NAME, key: PROJECTS_KEY });

    // S3からCSVファイルを取得
    const command = new GetObjectCommand({
      Bucket: BUCKET_NAME,
      Key: PROJECTS_KEY,
    });

    const response = await s3Client.send(command);
    const csvContent = await response.Body?.transformToString();

    if (!csvContent) {
      throw new Error('Empty CSV content');
    }

    // CSVをパース（ヘッダー行をスキップ）
    const lines = csvContent.trim().split('\n');
    const projects: Project[] = [];

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      const [id, name] = line.split(',');
      projects.push({
        id: parseInt(id, 10),
        name: name.trim(),
      });
    }

    console.log(`Successfully loaded ${projects.length} projects`);

    return {
      statusCode: 200,
      body: JSON.stringify(projects),
    };
  } catch (error) {
    console.error('Error fetching projects:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({
        error: 'Failed to fetch projects',
        message: error instanceof Error ? error.message : 'Unknown error',
      }),
    };
  }
};
