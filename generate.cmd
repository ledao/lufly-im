python .\scripts\generate_rime_lu_phone_xhe_shape.py check

python .\scripts\generate_rime_xhe_phone_xhe_shape.py
python .\scripts\generate_rime_xhe_phone_zrm_shape.py
python .\scripts\generate_rime_zrm_phone_xhe_shape.py
python .\scripts\generate_rime_zrm_phone_zrm_shape.py

python .\scripts\generate_dd_xhe_phone_xhe_shape.py
python .\scripts\generate_dd_xhe_phone_zrm_shape.py
python .\scripts\generate_dd_zrm_phone_xhe_shape.py
python .\scripts\generate_dd_zrm_phone_zrm_shape.py

powershell Compress-Archive -Force -Path ".\rime_xiaolu_shuangpin_xiaohe_xing" -DestinationPath "rime_xiaolu_shuangpin_xiaohe_xing.zip"

powershell Compress-Archive -Force -Path ".\rime_xiaohe_shuangpin_xiaohe_xing" -DestinationPath "rime_xiaohe_shuangpin_xiaohe_xing.zip"
powershell Compress-Archive -Force -Path ".\rime_ziranma_shuangpin_xiaohe_xing" -DestinationPath "rime_ziranma_shuangpin_xiaohe_xing.zip"
powershell Compress-Archive -Force -Path ".\rime_ziranma_shuangpin_ziranma_xing" -DestinationPath "rime_ziranma_shuangpin_ziranma_xing.zip"
powershell Compress-Archive -Force -Path ".\rime_xiaohe_shuangpin_ziranma_xing" -DestinationPath "rime_xiaohe_shuangpin_ziranma_xing.zip"

