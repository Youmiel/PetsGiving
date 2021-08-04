import enum
import os
import re
import time
from mcdreforged.api import rcon
from mcdreforged.api.all import *

PLUGIN_METADATA = {
    'id': 'pets_giving',
    'version': '0.1.2',
    'name': 'PetsGiving',
    'description': "A MCDR plugin that allows players to exchange their pets.",
    'author': ['Youmiel'],
    'link': 'https://github.com/Youmiel/PetsGiving-MCDR',
    'dependencies': {
		'mcdreforged': '>=1.0.0',
	}
}

# cat, wolf, parrot, horse, donkey, mule, lama - Owner
# fox - Trusted: list
# ocelot - No owner

CONFIG_PATH = os.path.join('config', 'PetsGiving.json')

class Fields():
    def __init__(self) -> None:
        self.server: ServerInterface

plugin_fields = Fields()

#-----------------------------------------
PETS = ['cat', 'wolf', 'parrot', 'horse', 'donkey', 'mule', 'lama', 'trader_lama', 'fox']

class PetCategory(enum.Enum):
    TAME_OWNER = ['horse', 'donkey', 'mule', 'lama', 'trader_lama']
    OWNER = ['cat', 'wolf', 'parrot']
    TRUSTED = ['fox']
    NONE = None

UUID_PATTERN = re.compile('[\w]+ has the following entity data: (\[I;[0-9\s,-]+\])')
FOX_PATTERN = re.compile('[\S]+ has the following entity data: \[(\[I;[0-9\s,-]+\])(,\s)?(\[I;[0-9\s,-]+\])?\]')
#-----------------------------------------
@new_thread('PetsGiving_checkRcon')
def check_rcon():
    global plugin_fields
    time.sleep(1)
    if plugin_fields.server.is_server_startup() and not plugin_fields.server.is_rcon_running():
        cast('no_rcon')()
        plugin_fields.server.unload_plugin(PLUGIN_METADATA['id'])

def cast(event: str):
    global plugin_fields
    server = plugin_fields.server
    func = {
        'fox_warn':lambda: server.broadcast('§eFox modifier are not fully supported, this may result in unpredictable behaviors.'),
        'custom':lambda string: server.broadcast(string),
        'player_offline': lambda src,player: src.reply('§c%s is not online.'%player),
        'console_warning': lambda: server.logger.warning('Console command is not supported.'),
        'no_rcon': lambda: server.logger.warning('RCON is not enabled, unloading plugin.'),
        'thing': lambda: server.logger.info('something\n')
    }[event]
    return func

@new_thread('send_pet')
def send_pet(cmd_src: CommandSource, pet_in: str, pet_name: str, target :str): 
    global plugin_fields
    if cmd_src.is_player == False:
        cast('console_waring')()
        return
    pet = convert_pets(pet_in)
    if pet is None:
        return
    cast('custom')('check passed')
    source_str = plugin_fields.server.rcon_query('data get entity %s UUID'%cmd_src.player)
    target_str = plugin_fields.server.rcon_query('data get entity %s UUID'%target)
    source_match = re.match(UUID_PATTERN, source_str)
    target_match = re.match(UUID_PATTERN, target_str)
    if source_match is not None:
        sourceUUID = source_match.group(1)
    if target_match is not None:
        targetUUID = target_match.group(1)
    else:
        cast('player_offline')(cmd_src, target)
        return
    command  = None
    if pet in PetCategory.TAME_OWNER.value:
        cast('custom')('check %s'%PetCategory.TAME_OWNER.__str__())
        command = 'execute at %s '%cmd_src.player +\
        'as @e[type=minecraft:%s,distance=..10,name=\"%s\",nbt={Tame:1b,Owner:%s}] '%(pet, pet_name, sourceUUID) +\
        'run data modify entity @s Owner set value %s'%targetUUID
    elif pet in PetCategory.OWNER.value:
        cast('custom')('check %s'%PetCategory.OWNER.__str__())
        command = 'execute at %s '%cmd_src.player +\
         'as @e[type=minecraft:%s,distance=..10,name=\"%s\",nbt={Owner:%s}] '%(pet, pet_name, sourceUUID) +\
         'run data modify entity @s Owner set value %s'%targetUUID
    elif pet in PetCategory.TRUSTED.value:
        cast('fox_warn')()
        tag = str(int(time.time()))
        mark = 'PetsGiving'
        server = plugin_fields.server
        server.rcon_query(
            'execute at %s as @e[type=minecraft:%s,distance=..10,name=\"%s\"] '%(cmd_src.player,pet, pet_name) +\
            'if data entity @s Trusted run tag @s add %s'%tag
        )
        while(server.rcon_query('execute if entity @e[tag=%s]'%tag) != 'Test failed'):
            server.rcon_query('tag @e[tag=%s,limit=1] add %s'%(tag,mark))
            trusted_str = server.rcon_query('data get entity @e[tag=%s,limit=1] Trusted'%mark)
            trusted_match = re.match(FOX_PATTERN,trusted_str)
            if trusted_match is not None:
                trustedUUID_1 = trusted_match.group(1)
                trustedUUID_2 = trusted_match.group(3)
            else:
                server.rcon_query('tag @e[tag=%s] remove %s'%(mark,tag))
                server.rcon_query('tag @e[tag=%s] remove %s'%(mark,mark))
                continue
            # ^ get trusted UUID
            UUID1 = trustedUUID_1
            UUID2 = trustedUUID_2
            if sourceUUID == trustedUUID_1:
                UUID1 = targetUUID
            elif sourceUUID == trustedUUID_2:
                UUID2 = targetUUID
            else:
                server.rcon_query('tag @e[tag=%s] remove %s'%(mark,tag))
                server.rcon_query('tag @e[tag=%s] remove %s'%(mark,mark))
                continue
            if UUID1 == UUID2:
                UUID2 = None
            # ^ replace UUID
            '''
            if UUID2 is None:
                set_command = 'data modify entity @e[tag=%s,tag=%s,limit=1] Trusted set value [%s]'%(tag,mark,UUID1)
            else:
                set_command = 'data modify entity @e[tag=%s,tag=%s,limit=1] Trusted set value [%s,%s]'%(tag,mark,UUID1,UUID2)
            '''

            # temp solution due to some (bugs?), the first uuid in Trusted list cannot be replaced by /data
            if (targetUUID == trustedUUID_1 and sourceUUID == trustedUUID_2) or (sourceUUID == trustedUUID_1 and targetUUID == trustedUUID_2):
                set_command = 'list' # dummy
            elif sourceUUID == trustedUUID_1 and trustedUUID_2 is None:
                set_command = 'data modify entity @e[tag=%s,tag=%s,limit=1] Trusted set value [%s]'%(tag,mark,targetUUID)
            elif sourceUUID == trustedUUID_1 or sourceUUID == trustedUUID_2:
                set_command = 'data modify entity @e[tag=%s,tag=%s,limit=1] Trusted[1] set value %s'%(tag,mark,targetUUID)
            else:
                set_command = 'list' # dummy

            server.rcon_query(set_command)
            server.rcon_query('tag @e[tag=%s] remove %s'%(mark,tag))
            server.rcon_query('tag @e[tag=%s] remove %s'%(mark,mark))

    if command != None:
        plugin_fields.server.rcon_query(command)

@new_thread('rob_pet')
def rob_pet(cmd_src: CommandSource, pet_in: str, pet_name: str):
    global plugin_fields
    if cmd_src.is_player == False:
        cast('console_waring')()
        return
    pet = convert_pets(pet_in)
    if pet is None:
        return
    source_str = plugin_fields.server.rcon_query('data get entity %s UUID'%cmd_src.player)
    source_match = re.match(UUID_PATTERN, source_str)
    if source_match is not None:
        sourceUUID = source_match.group(1)
    command  = None
    if pet in PetCategory.TAME_OWNER.value:
        command = 'execute at %s '%cmd_src.player +\
        'as @e[type=minecraft:%s,distance=..10,name=\"%s\",nbt={Tame:1b}] '%(pet, pet_name) +\
        'run data modify entity @s Owner set value %s'%sourceUUID
    elif pet in PetCategory.OWNER.value:
        command = 'execute at %s '%cmd_src.player +\
        'as @e[type=minecraft:%s,distance=..10,name=\"%s\"] '%(pet, pet_name) +\
        'if data entity @s Owner ' +\
        'run data modify entity @s Owner set value %s'%sourceUUID
    elif pet in PetCategory.TRUSTED.value:
        cast('fox_warn')()
        tag = str(int(time.time()))
        mark = 'PetsRobbing'
        server = plugin_fields.server
        server.rcon_query(
            'execute at %s as @e[type=minecraft:%s,distance=..10,name=\"%s\"] '%(cmd_src.player,pet, pet_name) +\
            'if data entity @s Trusted run tag @s add %s'%tag
        )
        while(server.rcon_query('execute if entity @e[tag=%s]'%tag) != 'Test failed'):
            server.rcon_query('tag @e[tag=%s,limit=1] add %s'%(tag,mark))
            trusted_str = server.rcon_query('data get entity @e[tag=%s,limit=1] Trusted'%mark)
            trusted_match = re.match(FOX_PATTERN,trusted_str)
            trustedUUID_1 = ''
            trustedUUID_2 = ''
            if trusted_match is not None:
                trustedUUID_1 = trusted_match.group(1)
                trustedUUID_2 = trusted_match.group(3)
            else:
                server.rcon_query('tag @e[tag=%s] remove %s'%(mark,tag))
                server.rcon_query('tag @e[tag=%s] remove %s'%(mark,mark))
                continue
            # ^ get trusted UUID
            UUID1 = sourceUUID
            UUID2 = trustedUUID_1
            if UUID1 == UUID2:
                UUID2 = None

            # ^ replace UUID
            '''
            if UUID2 is None:
                set_command = 'data modify entity @e[tag=%s,tag=%s,limit=1] Trusted set value [%s]'%(tag,mark,UUID1)
            else:
                set_command = 'data modify entity @e[tag=%s,tag=%s,limit=1] Trusted set value [%s,%s]'%(tag,mark,UUID1,UUID2)
            '''

            # temp solution due to some (bugs?), the first uuid in Trusted list cannot be replaced by /data
            if sourceUUID == trustedUUID_1 or sourceUUID == trustedUUID_2:
                set_command = 'list' # dummy
            elif trustedUUID_2 is None:
                set_command = 'data modify entity @e[tag=%s,tag=%s,limit=1] Trusted set value [%s]'%(tag,mark,sourceUUID)
            else:
                set_command = 'data modify entity @e[tag=%s,tag=%s,limit=1] Trusted[1] set value %s'%(tag,mark,sourceUUID)

            server.rcon_query(set_command)
            server.rcon_query('tag @e[tag=%s] remove %s'%(mark,tag))
            server.rcon_query('tag @e[tag=%s] remove %s'%(mark,mark))
            # ^ set UUID

    if command != None:
        plugin_fields.server.rcon_query(command)

def convert_pets(pet: str) -> str:
    global PETS
    if pet.lower() in PETS:
        return pet.lower()
    else: 
        return None
#-----------------------------------------
def on_load(server: ServerInterface, old_state):
    global plugin_fields, config
    if old_state is not None:
        plugin_fields = old_state.plugin_fields
    plugin_fields.server = server
    if server.is_server_running():
        check_rcon()
    reg_commands()
    pass

def reg_commands():
    global plugin_fields
    server = plugin_fields.server
    '''
    !!sendpet <pet_category> <pet_name> to <online_player>
    !!robpet <pet_category> <pet_name>
    '''
    server.register_command(
        Literal('!!sendpet').
        runs(lambda src: server.reply(src.get_info(),'§eUsage: !!sendpet <pet_category> <pet_name> to <online_player>')).
        then(
            Text('pet_in').
            requires(lambda src,ctx: ctx['pet_in'].lower() in PETS).
            then(
                Text('pet_name').
                then(
                    Literal('to').
                    then(
                        Text('online_player')
                        .runs(lambda src,ctx: send_pet(src,ctx['pet_in'],ctx['pet_name'],ctx['online_player']))
                    )
                )
            )
        )
    )
    server.register_command(
        Literal('!!robpet').
        runs(lambda src: server.reply(src.get_info(),'§eUsage: !!robpet <pet_category> <pet_name>')).
        requires(lambda src: src.has_permission(3)).
        then(
            Text('pet_in').
            requires(lambda src,ctx: ctx['pet_in'].lower() in PETS).
            then(
                Text('pet_name').
                runs(lambda src,ctx: rob_pet(src,ctx['pet_in'],ctx['pet_name']))                
            )
        )
    )

def on_server_startup(server: ServerInterface):
    check_rcon()