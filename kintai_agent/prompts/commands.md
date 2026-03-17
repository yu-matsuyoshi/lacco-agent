# OA Lacco APP コマンドリファレンス

## 1. 工数登録（add）

### 単日登録
```
OA Lacco APP add <日付> <案件ID> <区分ID> <割合>%
```
例: `OA Lacco APP add 2026/02/18 12345 1 100%`

### 月全体に一括登録 (-r)
```
OA Lacco APP add -r <年月> <案件ID> <区分ID> <割合>%
```
例: `OA Lacco APP add -r 2026/02 12345 1 50%`
※ 指定月の全営業日に登録

### 開始日から指定日数分登録 (-t)
```
OA Lacco APP add -t <繰り返し日数> <日付> <案件ID> <区分ID> <割合>%
```
例: `OA Lacco APP add -t 10 2026/02/18 12345 1 50%`
※ 繰り返し日数は2〜20まで有効

### 開始日から終了日まで登録 (-u)
```
OA Lacco APP add -u <終了日> <開始日> <案件ID> <区分ID> <割合>%
```
例: `OA Lacco APP add -u 2026/02/28 2026/02/18 12345 1 50%`
※ 繰り返し可能な営業日数は20日まで

## 2. コピー（cp）
```
OA Lacco APP cp <コピー元日付> <コピー先日付>
```
例: `OA Lacco APP cp 2026/02/17 2026/02/18`
※ `.` を指定すると今日の日付として解釈
例: `OA Lacco APP cp 2026/02/17 .`

## 3. 削除（rm）

### 日毎に削除
```
OA Lacco APP rm <日付>
```
例: `OA Lacco APP rm 2026/02/18`

### 月毎に削除
```
OA Lacco APP rm <年月>
```
例: `OA Lacco APP rm 2026/02`

## 4. 確認（ls）

### 日付指定で確認
```
OA Lacco APP ls /data/<日付>
```
例: `OA Lacco APP ls /data/2026/02/18`

### 月指定で確認
```
OA Lacco APP ls /data/<年月>
```
例: `OA Lacco APP ls /data/2026/02`

### 今月の工数確認
```
OA Lacco APP ls now
```
