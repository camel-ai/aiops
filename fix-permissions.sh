#!/bin/bash

# MCDP 权限修复脚本
# 如果脚本没有执行权限，可以手动运行此脚本

echo "🔧 正在修复MCDP脚本权限..."

# 修复所有shell脚本的权限
for script in build-and-push.sh deploy.sh fix-permissions.sh; do
    if [ -f "$script" ]; then
        chmod +x "$script"
        echo "✅ 已修复: $script"
    else
        echo "⚠️  文件不存在: $script"
    fi
done

echo "🎉 权限修复完成！"
echo ""
echo "现在可以直接运行："
echo "  ./build-and-push.sh v1.0.0    # 构建镜像"
echo "  ./deploy.sh                   # 部署应用" 