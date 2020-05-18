#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import re
import tempfile

# import module snippets
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_bytes, to_native

def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str'),
        ),
        mutually_exclusive=[['insertbefore', 'insertafter']],
        add_file_common_args=True,
        supports_check_mode=True,
    )
    params = module.params
    name = params['name']
    if name is None:
        module.fail_json(msg='name is required')
    proc = subprocess.call(["zpool", name, 'status'])
    


if __name__ == '__main__':
    main()