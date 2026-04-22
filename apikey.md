Windows（PowerShell）

当前窗口有效：
$env:DASHSCOPE_API_KEY="你的key"
长期生效（当前用户）：
[Environment]::SetEnvironmentVariable("DASHSCOPE_API_KEY","你的key","User")
验证：
echo $env:DASHSCOPE_API_KEY
说明：长期生效要新开终端才会读到。
Windows（CMD）

当前窗口有效：
set DASHSCOPE_API_KEY=你的key
长期生效：
setx DASHSCOPE_API_KEY "你的key"
验证：
echo %DASHSCOPE_API_KEY%


Ubuntu（bash/zsh）

加到 ~/.bashrc（bash）或 ~/.zshrc（zsh）：
nano ~/.zshrc
export DASHSCOPE_API_KEY='你的key'
生效：
source ~/.bashrc   # 或 source ~/.zshrc
验证：
echo "$DASHSCOPE_API_KEY"


macOS（zsh 默认）

加到 ~/.zshrc：
nano ~/.zshrc
export DASHSCOPE_API_KEY='你的key'
生效：
source ~/.zshrc
验证：
echo "$DASHSCOPE_API_KEY"
不要把 key 写进 Git 提交（比如 app.example.json）。

