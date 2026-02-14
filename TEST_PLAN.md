# Fast Edit 测试计划

## 测试环境

```bash
FE="python3 /Users/wudi/data/code/ai_tools/git_skills/wudi/fast-edit/fast_edit.py"
TEST_DIR="/tmp/fast-edit-test"
mkdir -p $TEST_DIR
```

## 测试用例

### 1. show - 预览行

```bash
# 创建测试文件
cat > $TEST_DIR/test.py << 'EOF'
# line 1
def hello():
    print("hello")  # line 3

def world():
    print("world")  # line 6
EOF

# 测试: 显示 2-4 行
$FE show $TEST_DIR/test.py 2 4

# 预期输出:
# 2: def hello():
# 3:     print("hello")  # line 3
# 4: 
```

✅ 通过条件: 输出包含行号 2-4，内容正确

---

### 2. replace - 替换行

```bash
# 测试: 替换第 3 行
$FE replace $TEST_DIR/test.py 3 3 '    print("replaced")\n'

# 验证
$FE show $TEST_DIR/test.py 2 4

# 预期: 第 3 行变为 print("replaced")
```

✅ 通过条件: 第 3 行内容已替换，其他行不变

---

### 3. insert - 插入行

```bash
# 重置测试文件
cat > $TEST_DIR/test.py << 'EOF'
# line 1
def hello():
    pass
EOF

# 测试: 在第 2 行后插入
$FE insert $TEST_DIR/test.py 2 '    """docstring"""\n'

# 验证
$FE show $TEST_DIR/test.py 1 5

# 预期: 第 3 行是 """docstring"""
```

✅ 通过条件: 新行插入在正确位置

```bash
# 测试: LINE=0 在开头插入
$FE insert $TEST_DIR/test.py 0 '#!/usr/bin/env python3\n'

# 验证
$FE show $TEST_DIR/test.py 1 2

# 预期: 第 1 行是 shebang
```

✅ 通过条件: shebang 在文件开头

---

### 4. delete - 删除行

```bash
# 重置测试文件
cat > $TEST_DIR/test.py << 'EOF'
line1
line2
line3
line4
line5
EOF

# 测试: 删除 2-4 行
$FE delete $TEST_DIR/test.py 2 4

# 验证
cat $TEST_DIR/test.py

# 预期输出:
# line1
# line5
```

✅ 通过条件: 只剩 line1 和 line5

---

### 5. batch - 批量编辑

```bash
# 重置测试文件
cat > $TEST_DIR/test.py << 'EOF'
def a():
    pass

def b():
    pass

def c():
    pass
EOF

# 测试: 多处编辑
$FE batch --stdin << 'EOF'
{
  "file": "/tmp/fast-edit-test/test.py",
  "edits": [
    {"action": "replace-lines", "start": 2, "end": 2, "content": "    return 'a'\n"},
    {"action": "replace-lines", "start": 5, "end": 5, "content": "    return 'b'\n"},
    {"action": "insert-after", "line": 8, "content": "\ndef d():\n    return 'd'\n"}
  ]
}
EOF

# 验证
cat $TEST_DIR/test.py

# 预期: 三处都修改成功
```

✅ 通过条件: 所有编辑按正确顺序应用

---

### 6. paste --stdin - 从 stdin 粘贴

```bash
# 测试: 保存内容到文件
echo 'print("hello from stdin")' | $FE paste $TEST_DIR/from_stdin.py --stdin

# 验证
cat $TEST_DIR/from_stdin.py

# 预期: print("hello from stdin")
```

✅ 通过条件: 文件内容与输入一致

---

### 7. paste --stdin --extract - 提取代码块

```bash
# 测试: 提取 markdown 代码块
$FE paste $TEST_DIR/extracted.py --stdin --extract << 'EOF'
这是一些说明文字

```python
def extracted():
    return "success"
```

更多文字
EOF

# 验证
cat $TEST_DIR/extracted.py

# 预期: 只有 def extracted(): ... 没有 ``` 标记
```

✅ 通过条件: 只提取代码块内容，无 markdown 标记

---

### 8. write --stdin - 批量写多文件

```bash
# 测试: 一次写入多个文件
$FE write --stdin << 'EOF'
{
  "files": [
    {"file": "/tmp/fast-edit-test/multi_a.py", "content": "def a(): pass\n"},
    {"file": "/tmp/fast-edit-test/multi_b.py", "content": "def b(): pass\n"},
    {"file": "/tmp/fast-edit-test/multi_c.py", "content": "```python\ndef c(): pass\n```", "extract": true}
  ]
}
EOF

# 验证
cat $TEST_DIR/multi_a.py
cat $TEST_DIR/multi_b.py
cat $TEST_DIR/multi_c.py

# 预期: 三个文件都创建成功，multi_c.py 提取了代码块
```

✅ 通过条件: 三个文件内容正确，extract 生效

---

### 9. check - 类型检查

```bash
# 测试: 正确的代码
cat > $TEST_DIR/good.py << 'EOF'
def add(a: int, b: int) -> int:
    return a + b
EOF

$FE check $TEST_DIR/good.py
echo "Exit code: $?"

# 预期: 无输出，退出码 0
```

✅ 通过条件: 退出码 0

```bash
# 测试: 有类型错误的代码
cat > $TEST_DIR/bad.py << 'EOF'
def add(a: int, b: int) -> int:
    return "not an int"
EOF

$FE check $TEST_DIR/bad.py
echo "Exit code: $?"

# 预期: 报告类型错误，退出码 1
```

✅ 通过条件: 报告错误，退出码 1

---

### 10. paste --stdin --base64 - base64 解码

```bash
# 测试: 含特殊字符的代码
# 原始内容: print('hello $USER')
# base64 编码: cHJpbnQoJ2hlbGxvICRVU0VSJyk=

echo 'cHJpbnQoJ2hlbGxvICRVU0VSJyk=' | $FE paste $TEST_DIR/b64_test.py --stdin --base64

# 验证
cat $TEST_DIR/b64_test.py

# 预期: print('hello $USER')  (不是 $USER 被展开后的值)
```

✅ 通过条件: 特殊字符 `$USER` 保持原样，没有被 shell 展开

```bash
# 测试: 含换行的多行代码
# 原始内容:
# def foo():
#     return "bar"
# base64: ZGVmIGZvbygpOgogICAgcmV0dXJuICJiYXIiCg==

echo 'ZGVmIGZvbygpOgogICAgcmV0dXJuICJiYXIiCg==' | $FE paste $TEST_DIR/b64_multiline.py --stdin --base64

# 验证
cat $TEST_DIR/b64_multiline.py

# 预期: 正确的两行 Python 代码
```

✅ 通过条件: 换行符正确还原

---

### 11. write --stdin 带 encoding: base64

```bash
# 测试: 批量写入，部分文件用 base64
$FE write --stdin << 'EOF'
{
  "files": [
    {"file": "/tmp/fast-edit-test/w_plain.py", "content": "def plain(): pass\n"},
    {"file": "/tmp/fast-edit-test/w_b64.py", "content": "ZGVmIGI2NCgpOiBwYXNzCg==", "encoding": "base64"}
  ]
}
EOF

# 验证
cat $TEST_DIR/w_plain.py
cat $TEST_DIR/w_b64.py

# 预期: 
# w_plain.py: def plain(): pass
# w_b64.py: def b64(): pass
```

✅ 通过条件: 两个文件都正确写入，base64 解码成功

---

## 清理

```bash
rm -rf $TEST_DIR
```

---

## 测试结果记录

| 命令 | 状态 | 备注 |
|------|------|------|
| show | ✅ | |
| replace | ✅ | |
| insert | ✅ | |
| delete | ✅ | |
| batch | ✅ | |
| paste --stdin | ✅ | |
| paste --stdin --extract | ✅ | |
| write --stdin | ✅ | |
| check | ✅ | |

| paste --stdin --base64 | ✅ | |
| write --stdin + encoding:base64 | ✅ | |

**全部测试通过**: 2025-02-14
