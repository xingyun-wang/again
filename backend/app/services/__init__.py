"""业务 service 层（M1-B B.3：v0.5 §9.1 + §10 M1 范围）。

按业务域拆 service：
- textbook_upload：教材上传 + PDF 抽取（M1-B B.3）
- 后续 M2 homework / M3 upload 等按需加

设计要点：
- service 接受 db Session（与 router 同事务/调用方决定事务边界）
- 不依赖 FastAPI / HTTPException（业务异常用领域异常；router 转 HTTP）
- 不修改已存在的 extractor（按 spec：adapter in service，不动 extractor 内部逻辑）
"""