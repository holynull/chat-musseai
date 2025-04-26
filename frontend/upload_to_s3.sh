#!/bin/bash

# 定义变量
BUCKET_NAME="musse.ai"
FOLDER_PATH="out"

# 检查文件夹是否存在
if [ ! -d "$FOLDER_PATH" ]; then
    echo "Folder $FOLDER_PATH does not exist."
    exit 1
fi

# 上传文件夹中的所有内容到 S3
aws s3 cp $FOLDER_PATH s3://$BUCKET_NAME/ --recursive

# 检查上传结果
if [ $? -eq 0 ]; then
    echo "All files uploaded successfully."
else
    echo "File upload failed."
fi