#!/usr/bin/python
#coding:utf-8
import lldb
import commands
import optparse
import shlex
import re
import fblldbbase as fb
import string

# 获取ASLR偏移地址
def get_ASLR():
    # 获取'image list -o'命令的返回结果
    interpreter = lldb.debugger.GetCommandInterpreter()
    returnObject = lldb.SBCommandReturnObject()
    interpreter.HandleCommand('image list -o -f', returnObject)
    output = returnObject.GetOutput();
    # 正则匹配出第一个0x开头的16进制地址
    #match = re.match(r'.+(0x[0-9a-fA-F]+)', output)
    match = re.search(r'.+(0x[0-9a-fA-F]{16})./var/containers', output)
    if match:
        return match.group(1)
    else:
        return None
# Super breakpoint
def sbr(debugger, command, result, internal_dict):
    #用户是否输入了地址参数
    if not command:
        print >>result, 'Please input the address!'
        return
    ASLR = get_ASLR()
    if ASLR:
        #如果找到了ASLR偏移，就设置断点
        debugger.HandleCommand('br set -a "%s+%s"' % (ASLR, command))
    else:
        print >>result, 'ASLR not found!'

def connectlocal(debugger, command, result, internal_dict):
    port = '7777'
    if command:
        port = command
    debugger.HandleCommand('process connect connect://localhost:%s' % port)

def gpmessage(debugger, command, result, internal_dict):
    tmp = """
        @import ObjectiveC.runtime;
        Class classA = NSClassFromString(@"$cls");
        NSMutableString *result = [NSMutableString string];
        if(classA) {
            GPBDescriptor *descriptor = objc_msgSend(classA,@selector(descriptor));
            NSString *firstLine = [NSString stringWithFormat:@"message %@ {\\n", descriptor.name]
            [result appendString:firstLine];
            NSMutableArray *enums = [NSMutableArray array];
            for (GPBFieldDescriptor *field in descriptor.fields) {
                NSMutableString *line = @"\\t".mutableCopy;
                if(field.fieldType == 1) {
                    [line appendString:@"repeated "];
                }
                switch (field.dataType) {
                    case 0x0:{
                    [line appendString:@"bool "];
                    break;
                    }
                    case 0x3: {
                    [line appendString:@"float "];
                    break;
                    }
                    case 0x6: {
                    [line appendString:@"double "];
                    break;
                    }
                    case 0x7:{
                    [line appendString:@"int32 "];
                    break;
                    }
                    case 0x8:{
                    [line appendString:@"int64 "];
                    break;
                    }
                    case 0xb:{
                    [line appendString:@"uint32 "];
                    break;
                    }
                    case 0xc:{
                    [line appendString:@"uint64 "];
                    break;
                    }
                    case 0xd:{
                    [line appendString:@"bytes "];
                    break;
                    }
                    case 0xe:{
                    [line appendString:@"string "];
                    break;
                    }
                    case 0xf: {
                    [line appendString:[NSString stringWithFormat:@"%@ ", NSStringFromClass(field.msgClass)]];
                    break;
                    }
                    case 0x11:{
                    Ivar ivar = class_getInstanceVariable([GPBEnumDescriptor class], "valueCount_");
                    uint32_t valueCount = (uint32_t)(uintptr_t)object_getIvar(field.enumDescriptor, ivar);
                    Ivar ivar2 = class_getInstanceVariable([GPBEnumDescriptor class], "values_");
                    uint32_t* values = (uint32_t*)(uintptr_t)object_getIvar(field.enumDescriptor, ivar2);
                    for(int i = 0; i < valueCount; i++) {
                    }
                    [line appendString:[NSString stringWithFormat:@"%@ ", objc_msgSend(field.enumDescriptor,@selector(name))]];
                    [enums addObject:field];
                    break;
                    }
                    default: {
                    [line appendString:[NSString stringWithFormat:@"unk%@ ", @(field.dataType)]];
                    break;
                    }
                }
                [line appendString:[NSString stringWithFormat:@"%@ = %@", field.name, @(field.number)]];
                if([field isPackable]) {
                    [line appendString:@"[packed]"];
                }
                [line appendString:@";\\n"];
                [result appendString:line];
            }
            [result appendString:@"}\\n"];
            //打印所有枚举类型的proto
            for (GPBFieldDescriptor *field in enums) {
                [result appendString:@"\\n"];
                GPBEnumDescriptor *enumDescriptor = field.enumDescriptor;
                NSMutableString *enumMessage = [NSMutableString string];
                [enumMessage appendString:[NSString stringWithFormat:@"enum %@ {\\n", descriptor.name]];
                Ivar ivar = class_getInstanceVariable([GPBEnumDescriptor class], "valueCount_");
                uint32_t valueCount = (uint32_t)(uintptr_t)object_getIvar(enumDescriptor, ivar);
                Ivar ivar2 = class_getInstanceVariable([GPBEnumDescriptor class], "values_");
                uint32_t* values = (uint32_t*)(uintptr_t)object_getIvar(enumDescriptor, ivar2);
                for(uint32_t i = 0; i < valueCount; i++) {
                uint32_t value = values[i];
                NSString *name = [enumDescriptor enumNameForValue:value];
                NSString *line = [NSString stringWithFormat:@"\\t%@ = %@;\\n", name, @(value)];
                [enumMessage appendString:line];
                }
                [enumMessage appendString:@"}\\n"];
                [result appendString:enumMessage];
            }
        }
        else {
            result = @"class not exists";
        }
        RETURN(result);
        """
    code = string.Template(tmp).substitute(cls=command)
    result = fb.evaluate(code)
    print result

def test(debugger, command, result, internal_dict):
    print 'test command'

# And the initialization code to add your commands
def __lldb_init_module(debugger, internal_dict):
    # 'command script add sbr' : 给lldb增加一个'sbr'命令
    # '-f lisaike.sbr' : 该命令调用了sbr文件的sbr函数
    debugger.HandleCommand('e @import ObjectiveC.runtime')
    debugger.HandleCommand('command script add sbr -f lisaike.sbr')
    print 'The "sbr" python command has been installed and is ready for use.'
    debugger.HandleCommand('command script add connectlocal -f lisaike.connectlocal')
    print 'The "connectlocal" python command has been installed and is ready for use.'
    debugger.HandleCommand('command script add gpmessage -f lisaike.gpmessage')
    print 'The "gpmessage" python command has been installed and is ready for use.'

    debugger.HandleCommand('command script add mytest -f lisaike.test')

