# 运行依赖与来源

- 本發行版核心專案：<https://github.com/C-EXCITE-STUDIO/jianying-headless-windows>；
  原專案歸屬：<https://github.com/mcncarl/jianying-headless>。Skill 總目錄或安裝器
  不會自動提供核心執行環境。
- 剪映专业版是用户单独安装的闭源运行依赖。官方库、字体、效果包、缓存媒体和
  账号权益不随本 Skill 分发。内部接口调用不代表官方 SDK 或集成许可。
- macOS 橋接頭文件參考 MIT 授權的 <https://github.com/wenshui330/jy-draftc>。Windows 草稿建立器直接使用另行安裝的 Apache-2.0
  <https://github.com/aoguai/pyJianYingDraft> 固定 commit，套用核心儲存庫提供的兩份修補檔；歷史適配器亦曾使用 <https://github.com/GuanYixuan/pyJianYingDraft>。完整聲明與許可文字保留在核心專案，不宣稱與上游完全獨立。
- FFmpeg、Python、Xcode 與 Windows MSVC 是外部工具，各自條款仍適用。
- 显式指定新字体时需在执行脚本的 Python 环境中安装核心项目的
  `requirements-fonts.txt`（fontTools 4.60.2，MIT）。默认字体流程、普通编辑和
  已有快照验证不需要此可选解析器；字体文件不随源码分发。
- 可选 ASR 需要单独安装的执行器/Skill、服务访问权限和本次调用授权；本 Skill
  不包含令牌，也不从聊天、剪贴板或浏览器自动寻找凭据。

代码许可证只覆盖明示有权许可的部分，不授予剪映程序库、账号或媒体素材的权利。
本 Skill 的原創部分採用 [MIT 授權](../LICENSE)。第三方內容保留原有授權，
獨立安裝的剪映及其程式庫、帳號和素材不受本 Skill 的 MIT 授權涵蓋。
