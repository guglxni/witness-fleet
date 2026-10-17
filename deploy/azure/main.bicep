param location string = 'eastus'
param vmName string = 'vm-witness-fleet'
param vmSize string = 'Standard_D2as_v4'
param adminUsername string = 'fleetadmin'
param sshPublicKey string
param dnsLabel string = 'witness-fleet-guglxni'

var tags = { project: 'witness-fleet', purpose: 'bounded-simulation-demo' }
resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: '${vmName}-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      { name: 'https', properties: { priority: 100, protocol: 'Tcp', access: 'Allow', direction: 'Inbound', sourceAddressPrefix: 'Internet', sourcePortRange: '*', destinationAddressPrefix: '*', destinationPortRange: '443' } }
      { name: 'http-acme', properties: { priority: 110, protocol: 'Tcp', access: 'Allow', direction: 'Inbound', sourceAddressPrefix: 'Internet', sourcePortRange: '*', destinationAddressPrefix: '*', destinationPortRange: '80' } }
    ]
  }
}
resource pip 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: '${vmName}-ip'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: { publicIPAllocationMethod: 'Static', dnsSettings: { domainNameLabel: dnsLabel } }
}
resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: '${vmName}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: ['10.47.0.0/16'] }
    subnets: [{ name: 'demo', properties: { addressPrefix: '10.47.1.0/24', networkSecurityGroup: { id: nsg.id } } }]
  }
}
resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: '${vmName}-nic'
  location: location
  tags: tags
  properties: {
    ipConfigurations: [{ name: 'primary', properties: { privateIPAllocationMethod: 'Dynamic', subnet: { id: '${vnet.id}/subnets/demo' }, publicIPAddress: { id: pip.id } } }]
  }
}
resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: vmName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    hardwareProfile: { vmSize: vmSize }
    storageProfile: {
      imageReference: { publisher: 'Canonical', offer: '0001-com-ubuntu-server-jammy', sku: '22_04-lts-gen2', version: 'latest' }
      osDisk: { createOption: 'FromImage', diskSizeGB: 64, deleteOption: 'Detach', managedDisk: { storageAccountType: 'StandardSSD_LRS' } }
    }
    osProfile: {
      computerName: vmName
      adminUsername: adminUsername
      customData: base64(loadTextContent('cloud-init.yml'))
      linuxConfiguration: { disablePasswordAuthentication: true, ssh: { publicKeys: [{ path: '/home/${adminUsername}/.ssh/authorized_keys', keyData: sshPublicKey }] } }
    }
    networkProfile: { networkInterfaces: [{ id: nic.id, properties: { primary: true, deleteOption: 'Detach' } }] }
    diagnosticsProfile: { bootDiagnostics: { enabled: true } }
    securityProfile: { securityType: 'TrustedLaunch', uefiSettings: { secureBootEnabled: true, vTpmEnabled: true } }
  }
}
output demoHost string = pip.properties.dnsSettings.fqdn
output publicIp string = pip.properties.ipAddress
output vmPrincipalId string = vm.identity.principalId
output vmResourceId string = vm.id
