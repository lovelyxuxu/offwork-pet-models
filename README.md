# 下班搭子角色制作资料与工具

这里提供角色制作记录模板、视频转换脚本和原创示例角色。导出的 `.petpack` 可在 [下班搭子](https://github.com/lovelyxuxu/offwork-pet) 的角色管理中导入。仓库内容采用 [MIT](LICENSE)。

- [角色制作记录模板](templates/character-README.md)
- [原创示例角色源目录](examples/seed)
- [角色包格式和制作说明](https://github.com/lovelyxuxu/offwork-pet/blob/main/docs/%E8%A7%92%E8%89%B2%E5%8C%85%E5%88%B6%E4%BD%9C%E4%B8%8E%E4%BD%BF%E7%94%A8.md)

从桌宠主仓库目录执行 `python tools/character_pack.py build ../offwork-pet-models/examples/seed --output seed.petpack` 导出示例。

`tools/video_to_action.py` 需要 FFmpeg、Pillow、NumPy、SciPy。它接受静态渐变背景视频和透明待机参考图，输出透明帧及供手工合并的行为片段。执行 `python tools/video_to_action.py --help` 查看参数。
