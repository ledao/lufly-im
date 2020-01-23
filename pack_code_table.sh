#!/usr/bin/bash

if [ -d baidu_mobile_ini ]; then
    tar czvf baidu_mobile_int.tgz baidu_mobile_ini
    rm -rf baidu_mobile_ini
fi

if [ -d full_phone_xhe_shape ]; then
    tar czvf full_phone_xhe_shape.tgz full_phone_xhe_shape
    rm -rf full_phone_xhe_shape
fi

if [ -d lu_phone_xhe_shape ]; then
    tar czvf lu_phone_xhe_shape.tgz lu_phone_xhe_shape
    rm -rf lu_phone_xhe_shape
fi

if [ -d xhe_phone_xhe_shape ]; then
    tar czvf xhe_phone_xhe_shape.tgz xhe_phone_xhe_shape
    rm -rf xhe_phone_xhe_shape
fi

if [ -d xhe_phone_xhe_shape_ff ]; then
    tar czvf xhe_phone_xhe_shape_ff.tgz xhe_phone_xhe_shape_ff
    rm -rf xhe_phone_xhe_shape_ff
fi

if [ -d zrm_phone_xhe_shape ]; then
    tar czvf zrm_phone_xhe_shape.tgz zrm_phone_xhe_shape
    rm -rf zrm_phone_xhe_shape
fi

echo 'done'
exit 0;

